import json

import frappe
from frappe import _
from frappe.utils import cint, now_datetime, strip_html, time_diff_in_seconds

from onechat.automation.values import (
	as_text,
	minutes_of,
	plain,
	render,
	resolve,
	rules_match,
	validate_answer,
)

CONTACT = "OneChat Contact"
NOTE = "OneChat Note"
BUTTON_LIMIT = 3
LIST_LIMIT = 10
RETRIES = 2
SEND_LIMIT = 500


class Result:
	def __init__(self, handle=None, wait=None, minutes=None, end=False, output=None):
		self.handle = handle
		self.wait = wait
		self.minutes = minutes
		self.end = end
		self.output = output


def normalized(text):
	return " ".join(strip_html(as_text(text)).split()).lower()


def options_of(config, key, limit):
	rows = []
	for index, row in enumerate(config.get(key) or [], start=1):
		title = (row.get("title") or "").strip()
		if title:
			rows.append(
				{
					"id": row.get("id") or f"option-{index}",
					"title": title,
					"description": (row.get("description") or "").strip(),
				}
			)
	return rows[:limit]


def timeout_minutes(config):
	return minutes_of(config.get("timeout"), config.get("timeout_unit") or "hours") or None


def picked(options, event):
	message = event.get("message") or {}
	reply_id = message.get("reply_id")
	text = normalized(message.get("text"))
	for option in options:
		if reply_id and reply_id == option["id"]:
			return option
		if text and text == normalized(option["title"]):
			return option
	if text.isdigit() and 0 < int(text) <= len(options):
		return options[int(text) - 1]
	return None


def retry_or(run, node_id, handle, send):
	retries = run.state.setdefault("retries", {})
	count = retries.get(node_id, 0)
	if run.graph.has_output(node_id, handle) or count >= RETRIES:
		retries.pop(node_id, None)
		return Result(handle=handle)

	retries[node_id] = count + 1
	send()
	return Result(wait="Reply")


def trigger(run, node_id, config):
	return Result()


def send_message(run, node_id, config):
	text = render(config.get("text"), run.context)
	attach = config.get("attach")
	if attach:
		from onechat.onechat.doctype.onechat_media.onechat_media import media_type_of

		run.send(content_type=media_type_of(attach), message=text, attach=attach)
	else:
		if not text.strip():
			frappe.throw(_("Write the message to send."))
		run.send(content_type="text", message=text)
	return Result(output={"sent": text[:200]})


def send_choices(run, config, kind):
	options = options_of(
		config, "buttons" if kind == "button" else "rows", BUTTON_LIMIT if kind == "button" else LIST_LIMIT
	)
	if not options:
		frappe.throw(_("Add at least one option."))

	text = render(config.get("text"), run.context)
	if not text.strip():
		frappe.throw(_("Write the message shown above the options."))

	payload = {
		"type": kind,
		"header": render(config.get("header"), run.context),
		"footer": render(config.get("footer"), run.context),
		"button": render(config.get("button_label"), run.context) or _("Choose"),
		"options": options,
	}
	run.send(
		content_type="interactive", message=text, buttons=json.dumps(payload), options=options, kind=kind
	)
	return options


def send_buttons(run, node_id, config):
	send_choices(run, config, "button")
	return Result(wait="Reply", minutes=timeout_minutes(config))


def send_list(run, node_id, config):
	send_choices(run, config, "list")
	return Result(wait="Reply", minutes=timeout_minutes(config))


def resume_choices(run, node_id, config, event, kind):
	if event["kind"] == "timeout":
		return Result(handle="no_reply")

	options = options_of(
		config, "buttons" if kind == "button" else "rows", BUTTON_LIMIT if kind == "button" else LIST_LIMIT
	)
	choice = picked(options, event)
	if choice:
		run.state.get("retries", {}).pop(node_id, None)
		run.context.setdefault("answers", {})[config.get("save_as") or node_id] = choice["title"]
		run.context["choice"] = choice
		return Result(handle=choice["id"], output={"picked": choice["title"]})

	def nudge():
		run.send(
			content_type="text",
			message=render(config.get("retry_text"), run.context) or _("Please pick one of the options."),
		)
		send_choices(run, config, kind)

	return retry_or(run, node_id, "other", nudge)


def resume_buttons(run, node_id, config, event):
	return resume_choices(run, node_id, config, event, "button")


def resume_list(run, node_id, config, event):
	return resume_choices(run, node_id, config, event, "list")


def ask_question(run, node_id, config):
	text = render(config.get("text"), run.context)
	if not text.strip():
		frappe.throw(_("Write the question to ask."))
	if not (config.get("save_as") or "").strip():
		frappe.throw(_("Name the answer so later steps can use it."))

	run.send(content_type="text", message=text)
	return Result(wait="Reply", minutes=timeout_minutes(config))


def resume_question(run, node_id, config, event):
	if event["kind"] == "timeout":
		return Result(handle="no_reply")

	message = event.get("message") or {}
	ok, value = validate_answer(config.get("answer_type") or "text", message.get("text"))
	if ok:
		run.state.get("retries", {}).pop(node_id, None)
		run.context.setdefault("answers", {})[config["save_as"].strip()] = value
		return Result(handle="answered", output={"answer": value})

	def nudge():
		run.send(
			content_type="text",
			message=render(config.get("error_text"), run.context)
			or _("Sorry, that doesn't look right. Please try again."),
		)

	return retry_or(run, node_id, "invalid", nudge)


def send_template(run, node_id, config):
	template = config.get("template")
	if not template:
		frappe.throw(_("Pick a template."))

	values = [as_text(resolve(value, run.context)) for value in config.get("parameters") or []]
	body = json.dumps({str(index): value for index, value in enumerate(values, start=1)}) if values else None
	run.send(
		message_type="Template",
		use_template=1,
		template=template,
		message=_("Template message"),
		content_type="text",
		body_param=body,
	)
	return Result(output={"template": template})


def send_form(run, node_id, config):
	form = config.get("form")
	if not form:
		frappe.throw(_("Pick the form to send."))

	text = render(config.get("text"), run.context) or _("Please fill in this form.")
	run.send(
		content_type="flow", message=text, flow=form, flow_cta=render(config.get("cta"), run.context) or None
	)
	return Result(wait="Form", minutes=timeout_minutes(config))


def resume_form(run, node_id, config, event):
	if event["kind"] == "timeout":
		return Result(handle="no_reply")

	message = event.get("message") or {}
	if message.get("type") != "flow":

		def nudge():
			run.send(content_type="text", message=_("Please fill in the form above to continue."))

		result = retry_or(run, node_id, "other", nudge)
		if result.wait:
			result.wait = "Form"
		return result

	answers = {key: value for key, value in (message.get("form") or {}).items() if key != "flow_token"}
	run.context["form"] = answers
	run.context.setdefault("answers", {}).update(answers)
	if config.get("save_as"):
		run.context["answers"][config["save_as"]] = answers
	return Result(handle="submitted", output=answers)


def send_products(run, node_id, config):
	items = [
		code.strip() for code in as_text(resolve(config.get("items"), run.context)).split(",") if code.strip()
	]
	if not items:
		frappe.throw(_("List the item codes to send."))

	products = {
		"items": items[:30],
		"body": render(config.get("text"), run.context),
		"header": render(config.get("header"), run.context),
	}
	run.send(
		content_type="product" if len(items) == 1 else "product_list",
		message=products["body"] or _("Products"),
		products=json.dumps(products),
	)
	return Result(output={"items": items[:30]})


def contact_name(run):
	name = (run.context.get("contact") or {}).get("name")
	if not name and run.simulate:
		return "__test__"
	if not name:
		frappe.throw(
			_(
				"This step needs a conversation. Start the flow from a WhatsApp message or set a phone field on the trigger."
			)
		)
	return name


def publish(contact, **event):
	from onechat.inbox.conversations import publish as publish_contact

	publish_contact(contact, **event)


def assign_agent(run, node_id, config):
	contact = contact_name(run)
	mode = config.get("mode")
	team = config.get("team") if mode == "team" else None
	if run.simulate:
		if mode == "agent" and config.get("agent"):
			agent = frappe.utils.get_fullname(config["agent"])
		elif team:
			agent = _("the next available agent in {0}").format(team)
		else:
			agent = _("the next available agent")
		run.note(_("Assign the conversation to {0}").format(agent))
		return Result()

	if mode in ("round_robin", "team"):
		from onechat.inbox.routing import config as routing_config
		from onechat.inbox.routing import mark_assigned, next_agent

		agent = next_agent(routing_config(), team, contact)
		user = agent.user if agent else None
		if agent:
			mark_assigned(agent)
	else:
		user = config.get("agent")

	if not user:
		return Result(output={"assigned": None})

	from onechat.workspace.audit import track

	previous = frappe.db.get_value(CONTACT, contact, "assigned_to")
	values = {"assigned_to": user}
	if team:
		values["team"] = team
	frappe.db.set_value(CONTACT, contact, values, update_modified=False)
	track(CONTACT, contact, [("assigned_to", previous, user)])
	publish(contact, assigned=previous != user)
	return Result(output={"assigned": user})


def label_names(contact):
	return frappe.get_all(
		"OneChat Contact Label",
		filters={"parenttype": CONTACT, "parentfield": "labels", "parent": contact},
		pluck="label",
		order_by="idx asc",
	)


def change_labels(run, config, add):
	contact = contact_name(run)
	label = config.get("label")
	if not label:
		frappe.throw(_("Pick a label."))

	current = label_names(contact)
	wanted = (
		[*current, label] if add and label not in current else [name for name in current if name != label]
	)
	if wanted == current:
		return Result()
	if not run.effect(_("{0} the label {1}").format(_("Add") if add else _("Remove"), label)):
		return Result()

	from onechat.workspace.audit import track

	frappe.db.delete(
		"OneChat Contact Label", {"parenttype": CONTACT, "parentfield": "labels", "parent": contact}
	)
	for index, name in enumerate(wanted, start=1):
		frappe.get_doc(
			{
				"doctype": "OneChat Contact Label",
				"parent": contact,
				"parenttype": CONTACT,
				"parentfield": "labels",
				"idx": index,
				"label": name,
			}
		).db_insert()
	track(CONTACT, contact, [("labels", ", ".join(current), ", ".join(wanted))])
	publish(contact)
	return Result(output={"labels": wanted})


def add_label(run, node_id, config):
	return change_labels(run, config, True)


def remove_label(run, node_id, config):
	return change_labels(run, config, False)


def set_status(run, node_id, config):
	contact = contact_name(run)
	status = config.get("status") or "Resolved"
	if not run.effect(_("Mark the conversation {0}").format(_(status).lower())):
		return Result()

	from onechat.inbox import history
	from onechat.inbox.conversations import status_values
	from onechat.workspace.audit import track

	previous = frappe.db.get_value(CONTACT, contact, "conversation_status")
	frappe.db.set_value(CONTACT, contact, status_values(status), update_modified=False)
	track(CONTACT, contact, [("conversation_status", previous, status)])
	if status == "Resolved":
		history.resolved(contact)
	publish(contact)
	return Result(output={"status": status})


def add_note(run, node_id, config):
	contact = contact_name(run)
	text = render(config.get("text"), run.context).strip()
	if not text:
		frappe.throw(_("Write the note."))
	if not run.effect(_("Add a note for the team: {0}").format(text[:120])):
		return Result()

	from onechat.inbox.conversations import note_html

	frappe.get_doc(
		{
			"doctype": NOTE,
			"reference_doctype": CONTACT,
			"reference_docname": contact,
			"content": note_html(text),
		}
	).insert(ignore_permissions=True)
	return Result(output={"note": text[:200]})


def handover(run, node_id, config):
	text = render(config.get("text"), run.context)
	if text.strip():
		run.send(content_type="text", message=text)
	if config.get("note"):
		add_note(run, node_id, {"text": config["note"]})
	if config.get("agent") or config.get("mode") in ("round_robin", "team"):
		assign_agent(run, node_id, config)
	contact = run.context.get("contact", {}).get("name")
	if contact:
		set_status(run, node_id, {"status": "Open"})
		if not run.simulate:
			from onechat.inbox.service import start_clock

			start_clock(contact, now_datetime())
	run.stop_reason = _("Handed over to the team")
	return Result(end=True)


def update_contact(run, node_id, config):
	contact = contact_name(run)
	values = {key: resolve(value, run.context) for key, value in (config.get("fields") or {}).items() if key}
	meta = frappe.get_meta(CONTACT)
	values = {key: value for key, value in values.items() if meta.has_field(key)}
	if not values or not run.effect(_("Update the contact: {0}").format(", ".join(values))):
		return Result()

	if {"mobile_no", "email"} & set(values):
		doc = frappe.get_doc(CONTACT, contact)
		doc.update(values)
		doc.save(ignore_permissions=True)
	else:
		frappe.db.set_value(CONTACT, contact, values)
	run.context.setdefault("contact", {}).update(plain(values))
	publish(contact)
	return Result(output=values)


def in_business_hours(rule, context):
	from onechat.inbox.routing import config as routing_config
	from onechat.inbox.routing import is_open

	settings = routing_config()
	return not cint(settings.business_hours_enabled) or is_open(settings, now_datetime())


def has_label(rule, context):
	return (rule.get("value") or "") in (context.get("contact") or {}).get("labels", [])


EXTRA_RULES = {"in_business_hours": in_business_hours, "has_label": has_label}


def condition(run, node_id, config):
	if config.get("rules"):
		passed = rules_match(config, run.context, EXTRA_RULES)
	elif config.get("condition"):
		passed = run.legacy_condition(config["condition"])
	else:
		passed = True
	return Result(handle="true" if passed else "false", output={"passed": passed})


def wait(run, node_id, config):
	if config.get("mode") == "business_hours":
		from onechat.inbox.routing import config as routing_config
		from onechat.inbox.routing import is_open, next_change

		settings = routing_config()
		moment = now_datetime()
		if not cint(settings.business_hours_enabled) or is_open(settings, moment):
			return Result(output={"waited": 0})
		opens = next_change(settings, moment)
		minutes = max(int(time_diff_in_seconds(opens, moment) // 60) + 1, 1) if opens else 60
		return Result(wait="Timer", minutes=minutes)

	minutes = minutes_of(config.get("duration") or config.get("seconds"), config.get("unit") or "minutes")
	if config.get("unit") == "seconds":
		minutes = max(cint(config.get("duration")) // 60, 1)
	if not minutes:
		return Result()
	return Result(wait="Timer", minutes=minutes)


def resume_wait(run, node_id, config, event):
	return Result()


def end(run, node_id, config):
	return Result(end=True)


def find_record(run, node_id, config):
	doctype, field = config.get("doctype"), config.get("field")
	if not doctype or not field:
		frappe.throw(_("Pick what to search and which field to match."))

	value = resolve(config.get("value"), run.context)
	source = records_of(doctype)
	rows = (
		source.get_all(doctype, filters={field: value}, fields=["name"], order_by="modified desc", limit=1)
		if value not in (None, "")
		else []
	)
	key = config.get("save_as") or "record"
	if not rows:
		run.context.setdefault("records", {})[key] = None
		return Result(handle="not_found")

	record = plain(source.get_doc(doctype, rows[0].name))
	run.context.setdefault("records", {})[key] = record
	return Result(handle="found", output={"name": rows[0].name})


def records_of(doctype):
	from onechat.integrations.connection import source_for

	return source_for(doctype)


def record_values(run, config):
	return {key: resolve(value, run.context) for key, value in (config.get("fields") or {}).items() if key}


def create_record(run, node_id, config):
	doctype = config.get("doctype")
	if not doctype:
		frappe.throw(_("Pick what to create."))

	from onechat.automation import safety
	from onechat.integrations.phone import with_phones

	source = records_of(doctype)
	values = with_phones(doctype, record_values(run, config), source)
	key = config.get("save_as") or "created"

	existing = existing_record(source, doctype, config, values)
	if existing:
		if config.get("if_exists") == "update":
			changes = {
				field: value
				for field, value in values.items()
				if field != config.get("match_field") and not safety.empty(value)
			}
			if changes and run.effect(_("Update {0} {1}").format(_(doctype), existing)):
				source.update(doctype, existing, changes, ignore_permissions=True)
			action = "updated"
		else:
			action = "existing"
		run.context.setdefault("records", {})[key] = plain(source.get_doc(doctype, existing))
		return Result(output={"name": existing, "action": action})

	try:
		fields = safety.fields_of(doctype, source)
	except Exception:
		fields = {}
	missing = safety.missing_required(fields, values)
	if missing:
		frappe.throw(
			_("{0} needs {1}, but they are empty. Map them in this step or give them a default.").format(
				_(doctype), ", ".join(safety.label_of(fields, name) for name in missing)
			)
		)

	if not run.effect(_("Create a {0}").format(_(doctype))):
		run.context.setdefault("records", {})[key] = {"name": _("(test)"), **values}
		return Result()

	doc = source.insert({"doctype": doctype, **values}, ignore_permissions=True)
	run.context.setdefault("records", {})[key] = plain(doc)
	return Result(output={"name": doc.get("name"), "action": "created"})


def existing_record(source, doctype, config, values):
	mode, field = config.get("if_exists") or "create", config.get("match_field")
	if mode == "create" or not field:
		return None
	value = values.get(field)
	if value in (None, ""):
		return None
	rows = source.get_all(doctype, filters={field: value}, fields=["name"], order_by="modified desc", limit=1)
	return rows[0].get("name") if rows else None


def update_record(run, node_id, config):
	doctype = config.get("doctype")
	name = as_text(resolve(config.get("name"), run.context))
	if not doctype or not name:
		frappe.throw(_("Pick the record to update."))

	from onechat.integrations.phone import with_phones

	source = records_of(doctype)
	values = with_phones(doctype, record_values(run, config), source)
	if not values or not run.effect(_("Update {0} {1}").format(_(doctype), name)):
		return Result()

	source.update(doctype, name, values, ignore_permissions=True)
	return Result(output={"name": name})


def send_to_records(run, node_id, config):
	doctype, phone_field, template = config.get("doctype"), config.get("phone_field"), config.get("template")
	if not doctype or not phone_field or not template:
		frappe.throw(_("Pick the records, their phone field and a template."))

	filters = {
		key: resolve(value, run.context) for key, value in (config.get("filters") or {}).items() if key
	}
	limit = min(cint(config.get("limit")) or 100, SEND_LIMIT)
	records = records_of(doctype).get_all(doctype, filters=filters, fields=["*"], limit=limit)

	sent = 0
	for record in records:
		phone = record.get(phone_field)
		if not phone:
			continue
		scope = {**run.context, "record": plain(record)}
		values = [as_text(resolve(value, scope)) for value in config.get("parameters") or []]
		body = (
			json.dumps({str(index): value for index, value in enumerate(values, start=1)}) if values else None
		)
		if run.simulate:
			run.note(_("Would send {0} to {1}").format(template, phone))
			sent += 1
			continue
		try:
			run.send_to(
				phone,
				message_type="Template",
				use_template=1,
				template=template,
				message=_("Template message"),
				content_type="text",
				body_param=body,
				reference_doctype=doctype,
				reference_name=record.name,
			)
			sent += 1
		except Exception:
			frappe.log_error(title=f"OneChat flow: send to {doctype} {record.name}")

	return Result(output={"matched": len(records), "sent": sent})


def send_payment_link(run, node_id, config):
	doctype = config.get("doctype") or "Sales Invoice"
	name = as_text(resolve(config.get("document"), run.context)).strip()
	amount = as_text(resolve(config.get("amount"), run.context)).strip()
	if not name:
		frappe.throw(_("Pick the invoice or order to collect payment for."))
	if run.simulate:
		run.note(_("Would send a payment link for {0} {1}").format(_(doctype), name))
		return Result(output={"document": name})
	if not run.contact:
		frappe.throw(_("This flow has no customer to send the payment link to."))

	from onechat.integrations import links
	from onechat.integrations.payments import request_payment

	contact = links.view(run.contact, "erpnext")
	message = request_payment(
		contact,
		{
			"doctype": doctype,
			"name": name,
			"amount": amount or None,
			"message": render(config.get("text"), run.context),
		},
	)
	return Result(output={"document": name, "result": message})


STEPS = {
	"message_received": trigger,
	"button_clicked": trigger,
	"form_submitted": trigger,
	"order_placed": trigger,
	"chat_link_opened": trigger,
	"doc_event_trigger": trigger,
	"erpnext_doc_event_trigger": trigger,
	"scheduled_trigger": trigger,
	"manual_trigger": trigger,
	"whatsapp_trigger": trigger,
	"whatsapp_incoming_trigger": trigger,
	"send_message": send_message,
	"send_buttons": send_buttons,
	"send_list": send_list,
	"ask_question": ask_question,
	"send_template": send_template,
	"send_form": send_form,
	"send_products": send_products,
	"assign_agent": assign_agent,
	"add_label": add_label,
	"remove_label": remove_label,
	"set_status": set_status,
	"add_note": add_note,
	"handover": handover,
	"update_contact": update_contact,
	"condition": condition,
	"if_else": condition,
	"if_condition": condition,
	"wait": wait,
	"delay": wait,
	"end": end,
	"find_record": find_record,
	"create_record": create_record,
	"update_record": update_record,
	"send_to_records": send_to_records,
	"send_payment_link": send_payment_link,
}

RESUME = {
	"send_buttons": resume_buttons,
	"send_list": resume_list,
	"ask_question": resume_question,
	"send_form": resume_form,
	"wait": resume_wait,
	"delay": resume_wait,
}
