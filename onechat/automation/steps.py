import json
import re

import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime, strip_html, time_diff_in_seconds

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
MESSAGE = "OneChat Message"
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


def other_number(run, config):
	from onechat.integrations.phone import frappe_phone

	raw = as_text(resolve(config.get("to"), run.context)).strip()
	if not raw:
		return None
	digits = re.sub(r"\D", "", frappe_phone(raw))
	if len(digits) < 7:
		frappe.throw(_("{0} is not a phone number.").format(raw))
	return digits


def deliver(run, config, **values):
	to = other_number(run, config)
	if not to:
		return run.send(**values)
	if run.simulate:
		run.note(_("Sent to {0} instead of this chat").format(to))
		return run.send(**values)
	return run.send_to(to, **values)


def send_message(run, node_id, config):
	text = render(config.get("text"), run.context)
	attach = config.get("attach")
	if attach:
		from onechat.onechat.doctype.onechat_media.onechat_media import media_type_of

		deliver(run, config, content_type=media_type_of(attach), message=text, attach=attach)
	else:
		if not text.strip():
			frappe.throw(_("Write the message to send."))
		deliver(run, config, content_type="text", message=text)
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


def param_text(value):
	return re.sub(r"[ \t]{4,}", "   ", re.sub(r"\s*\n\s*", " · ", as_text(value))).strip()


def send_template(run, node_id, config):
	template = config.get("template")
	if not template:
		frappe.throw(_("Pick a template."))

	values = [param_text(resolve(value, run.context)) for value in config.get("parameters") or []]
	body = json.dumps({str(index): value for index, value in enumerate(values, start=1)}) if values else None
	deliver(
		run,
		config,
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


def table_rows(run, config):
	table = config.get("rows_field")
	if not table:
		return {}

	from onechat.automation.safety import empty

	entries = resolve(config.get("rows_from"), run.context)
	if isinstance(entries, str):
		entries = frappe.parse_json(entries) if entries.strip().startswith("[") else None
	if not isinstance(entries, list):
		frappe.throw(
			_("{0} is not a list, so the table rows cannot be built.").format(config.get("rows_from"))
		)

	rows = []
	for entry in entries:
		scope = {**run.context, "row": entry}
		values = {
			key: resolve(value, scope) for key, value in (config.get("row_fields") or {}).items() if key
		}
		row = {key: value for key, value in values.items() if not empty(value)}
		if row:
			rows.append(row)
	return {table: rows}


def create_record(run, node_id, config):
	doctype = config.get("doctype")
	if not doctype:
		frappe.throw(_("Pick what to create."))

	from onechat.automation import safety
	from onechat.integrations.phone import with_phones

	source = records_of(doctype)
	values = with_phones(doctype, record_values(run, config), source)
	values.update(table_rows(run, config))
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
		link_chat(run, config, doctype, existing)
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
		run.context.setdefault("records", {})[key] = {"doctype": doctype, "name": _("(test)"), **values}
		return Result()

	doc = source.insert({"doctype": doctype, **values}, ignore_permissions=True)
	run.context.setdefault("records", {})[key] = plain(doc)
	link_chat(run, config, doctype, doc.get("name"))
	return Result(output={"name": doc.get("name"), "action": "created"})


def link_chat(run, config, doctype, name):
	if not cint(config.get("link_contact")) or not run.contact or run.simulate:
		return

	from onechat.inbox.conversations import publish
	from onechat.integrations import links

	if links.owner(doctype):
		integration = links.add(run.contact, doctype, name, main=True)
		publish(run.contact)
		run.context["contact"].setdefault("links", {})[integration] = {"doctype": doctype, "name": name}


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

	filters = filter_values(run, config.get("filters"))
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


def keep_record(run, key, doctype, name):
	run.context.setdefault("records", {})[key] = plain(records_of(doctype).get_doc(doctype, name))


def filled_values(run, config, key):
	from onechat.automation.safety import empty

	values = {field: resolve(value, run.context) for field, value in (config.get(key) or {}).items() if field}
	return {field: value for field, value in values.items() if not empty(value)}


SAVED_NAME = re.compile(r"^\{\{\s*records\.(\w+)\.name\s*\}\}$")


def record_doctype(run, config, key, default=None):
	if not cint(config.get("same_as_record")):
		return config.get(key) or default
	match = SAVED_NAME.match((config.get("name") or "").strip())
	record = ((run.context.get("records") or {}).get(match.group(1)) or {}) if match else {}
	if not record.get("doctype"):
		frappe.throw(
			_("Pick the record type. {0} is not a record saved by an earlier step.").format(
				config.get("name") or _("The record")
			)
		)
	return record["doctype"]


def create_from_order(run, node_id, config):
	doctype = config.get("doctype") or "Sales Order"
	key = config.get("save_as") or "order"
	order = run.context.get("order") or {}
	if not run.effect(_("Create a {0} for this WhatsApp order").format(_(doctype))):
		run.context.setdefault("records", {})[key] = {
			"doctype": doctype,
			"name": _("(test)"),
			"grand_total": order.get("total"),
		}
		return Result(handle="done")

	if not order.get("message"):
		frappe.throw(_("Start this flow with Customer places an order to use this step."))

	from onechat.integrations import erpnext_commerce as commerce

	if not commerce.enabled():
		frappe.throw(_("Connect ERPNext in Settings → Integrations first."))

	message = frappe.get_doc(MESSAGE, order["message"])
	submit = cint(config.get("submit"))
	made = run.state.setdefault("from_order", {})
	name = made.get(doctype) or commerce.created_from(message, doctype)
	if not name:
		with commerce.elevated():
			name = commerce.create_from_order(
				message,
				doctype,
				extra=filled_values(run, config, "fields"),
				item_extra=filled_values(run, config, "item_fields"),
				submit=submit,
				days=config.get("delivery_days"),
			)
		if not name:
			return Result(handle="no_items", output={"unknown": order.get("unknown")})
		commerce.mark_order(message, name, doctype, submitted=submit)
	made[doctype] = name

	keep_record(run, key, doctype, name)
	return Result(handle="done", output={"name": name, "unknown": order.get("unknown")})


SELLING = "erpnext.selling.doctype"
BUYING = "erpnext.buying.doctype"
MAKERS = {
	("Quotation", "Sales Order"): f"{SELLING}.quotation.quotation.make_sales_order",
	("Quotation", "Sales Invoice"): f"{SELLING}.quotation.quotation.make_sales_invoice",
	("Sales Order", "Sales Invoice"): f"{SELLING}.sales_order.sales_order.make_sales_invoice",
	("Sales Order", "Delivery Note"): f"{SELLING}.sales_order.sales_order.make_delivery_note",
	("Sales Order", "Material Request"): f"{SELLING}.sales_order.sales_order.make_material_request",
	("Sales Order", "Pick List"): f"{SELLING}.sales_order.sales_order.create_pick_list",
	(
		"Delivery Note",
		"Sales Invoice",
	): "erpnext.stock.doctype.delivery_note.delivery_note.make_sales_invoice",
	(
		"Sales Invoice",
		"Delivery Note",
	): "erpnext.accounts.doctype.sales_invoice.sales_invoice.make_delivery_note",
	(
		"Material Request",
		"Purchase Order",
	): "erpnext.stock.doctype.material_request.material_request.make_purchase_order",
	("Purchase Order", "Purchase Receipt"): f"{BUYING}.purchase_order.purchase_order.make_purchase_receipt",
	("Purchase Order", "Purchase Invoice"): f"{BUYING}.purchase_order.purchase_order.make_purchase_invoice",
}
PAYMENT_ENTRY = "erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry"
PAYABLE = ("Sales Order", "Sales Invoice", "Purchase Order", "Purchase Invoice")


def maker(source_doctype, target, name):
	if target == "Payment Entry" and source_doctype in PAYABLE:
		return PAYMENT_ENTRY, {"dt": source_doctype, "dn": name}
	method = MAKERS.get((source_doctype, target))
	return (method, {"source_name": name}) if method else (None, None)


def make_record(run, node_id, config):
	source_doctype, target = record_doctype(run, config, "from_doctype", "Sales Order"), config.get("doctype")
	name = as_text(resolve(config.get("name"), run.context)).strip()
	method, args = maker(source_doctype, target, name)
	if not method:
		frappe.throw(_("A {0} cannot be made from a {1}.").format(_(target or ""), _(source_doctype)))
	if not name:
		frappe.throw(_("Pick the {0} to make it from.").format(_(source_doctype)))

	key = config.get("save_as") or "made"
	submit = cint(config.get("submit"))
	if not run.effect(_("Make a {0} from {1} {2}").format(_(target), _(source_doctype), name)):
		run.context.setdefault("records", {})[key] = {"doctype": target, "name": _("(test)")}
		return Result(handle="done")

	from onechat.integrations.erpnext_commerce import elevated

	source = records_of(target)
	values = record_values(run, config)
	with elevated():
		if source.remote:
			doc = source.call(method, **args)
			doc.update(values)
			doc = source.insert(doc)
			if submit:
				doc = source.submit(doc)
		else:
			doc = frappe.get_attr(method)(**args)
			doc.update(values)
			doc.insert(ignore_permissions=True)
			if submit:
				doc.submit()

	keep_record(run, key, target, doc.get("name"))
	return Result(handle="done", output={"name": doc.get("name")})


def change_status(source, doc, cancel):
	if source.remote and cancel:
		source.call("frappe.client.cancel", doctype=doc.doctype, name=doc.name)
	elif source.remote:
		source.submit(doc)
	else:
		record = frappe.get_doc(doc.doctype, doc.name)
		record.flags.ignore_permissions = True
		if cancel:
			record.cancel()
		else:
			record.submit()


def remove_record(source, doctype, name):
	if source.remote:
		source.call("frappe.client.delete", doctype=doctype, name=name)
	else:
		frappe.delete_doc(doctype, name, ignore_permissions=True)


def submit_record(run, node_id, config):
	doctype = record_doctype(run, config, "doctype")
	name = as_text(resolve(config.get("name"), run.context)).strip()
	action = config.get("action") or "submit"
	labels = {
		"submit": _("Submit {0} {1}"),
		"cancel": _("Cancel {0} {1}"),
		"delete": _("Delete {0} {1}"),
	}
	if action not in labels:
		frappe.throw(_("Pick submit, cancel or delete."))
	if not doctype or not name:
		frappe.throw(_("Pick the record to change."))
	if not run.effect(labels[action].format(_(doctype), name)):
		return Result(handle="done")

	from onechat.integrations.erpnext_commerce import elevated

	source = records_of(doctype)
	with elevated():
		doc = source.get_doc(doctype, name)
		status = cint(doc.get("docstatus"))
		if action == "cancel" and status == 0:
			action = "delete"
		if action == "submit" and status == 0:
			change_status(source, doc, cancel=False)
		elif action in ("cancel", "delete") and status == 1:
			change_status(source, doc, cancel=True)
		if action == "delete":
			remove_record(source, doctype, name)

	if config.get("save_as") and action != "delete":
		keep_record(run, config["save_as"], doctype, name)
	return Result(handle="done", output={"name": name, "action": action})


ADDRESS_FIELDS = {
	"Shipping": ("shipping_address_name", "shipping_address"),
	"Billing": ("customer_address", "address_display"),
}
BUYING_ADDRESS_FIELDS = {
	"Shipping": ("shipping_address", "shipping_address_display"),
	"Billing": ("supplier_address", "address_display"),
}
BUYING = ("Supplier Quotation", "Purchase Order", "Purchase Receipt", "Purchase Invoice")
PARTIES = ("Customer", "Supplier", "Lead")


def party_of(run):
	link = ((run.context.get("contact") or {}).get("links") or {}).get("erpnext") or {}
	if link.get("doctype") in PARTIES and link.get("name"):
		return link["doctype"], link["name"]

	from onechat.integrations.erpnext_commerce import customer_for

	return "Customer", customer_for(frappe.get_doc(CONTACT, run.contact))


def address_fields(doctype, kind, config):
	if config.get("address_field"):
		return config["address_field"], None
	fields = BUYING_ADDRESS_FIELDS if doctype in BUYING else ADDRESS_FIELDS
	return fields.get(kind, fields["Shipping"])


def save_address(run, node_id, config):
	kind = config.get("address_type") or "Shipping"
	values = record_values(run, config)
	key = config.get("save_as") or "address"
	if not run.effect(_("Save the customer's {0} address").format(_(kind).lower())):
		run.context.setdefault("records", {})[key] = {"name": _("(test)"), **values}
		return Result(handle="done")
	if not run.contact:
		frappe.throw(_("This flow has no customer to save the address for."))

	from onechat.automation import safety
	from onechat.integrations import erpnext_commerce as commerce

	source = records_of("Address")
	party_type, party = party_of(run)
	values.setdefault("country", source.single_value("System Settings", "country"))
	values.setdefault("phone", (run.context.get("contact") or {}).get("mobile_no"))
	values.setdefault("is_shipping_address" if kind == "Shipping" else "is_primary_address", 1)
	values = {
		"address_title": party,
		"address_type": kind,
		**{field: value for field, value in values.items() if not safety.empty(value)},
	}
	fields = safety.fields_of("Address", source)
	missing = safety.missing_required(fields, values)
	if missing:
		frappe.throw(
			_("The address needs {0}. Map them in this step.").format(
				", ".join(safety.label_of(fields, name) for name in missing)
			)
		)

	with commerce.elevated():
		address = source.insert(
			{"doctype": "Address", **values, "links": [{"link_doctype": party_type, "link_name": party}]},
			ignore_permissions=True,
		)
		document = as_text(resolve(config.get("document"), run.context)).strip()
		if document:
			doctype = config.get("doctype") or "Sales Order"
			target = records_of(doctype)
			name_field, display_field = address_fields(doctype, kind, config)
			changes = {name_field: address.name}
			if display_field:
				changes[display_field] = target.call(
					"frappe.contacts.doctype.address.address.get_address_display", address_dict=address.name
				)
			target.update(doctype, document, changes, ignore_permissions=True)

	run.context.setdefault("records", {})[key] = plain(address)
	return Result(handle="done", output={"name": address.name, "linked_to": f"{party_type} {party}"})


LEGACY_PATH = re.compile(r"^(context|doc)\.[\w.]+$")


def value_of(run, value):
	if isinstance(value, str) and LEGACY_PATH.match(value.strip()):
		from onechat.automation.node_executors import resolve_expression

		return resolve_expression(value.strip(), run.context)
	return resolve(value, run.context)


def text_of(run, value):
	return as_text(value_of(run, value)).strip()


def values_of(run, mapping):
	return {key: value_of(run, value) for key, value in (mapping or {}).items() if key}


FILTER_OPERATORS = (">=", "<=", "!=", ">", "<", "=")


def filter_value(value):
	if not isinstance(value, str):
		return value
	text = value.strip()
	lower = text.lower()
	if lower in ("is set", "set"):
		return ["is", "set"]
	if lower in ("is not set", "not set", "empty"):
		return ["is", "not set"]
	for word, operator in (
		("not in ", "not in"),
		("in ", "in"),
		("not like ", "not like"),
		("like ", "like"),
	):
		if lower.startswith(word):
			rest = text[len(word) :].strip()
			if operator.endswith("in"):
				return [operator, [part.strip() for part in rest.split(",") if part.strip()]]
			return [operator, rest]
	for operator in FILTER_OPERATORS:
		if text.startswith(operator):
			return [operator, text[len(operator) :].strip()]
	return value


def filter_values(run, mapping):
	return {key: filter_value(value) for key, value in values_of(run, mapping).items()}


def summarize_list(run, node_id, config):
	entries = value_of(run, config.get("list"))
	if isinstance(entries, str):
		entries = frappe.parse_json(entries) if entries.strip().startswith("[") else None
	entries = entries if isinstance(entries, list) else []
	line = config.get("line") or "{{row.name}}"
	limit = cint(config.get("limit")) or 20
	separator = {"comma": ", ", "semicolon": "; ", "dot": " · "}.get(
		config.get("separator") or "newline", "\n"
	)
	total_field = config.get("total_field")
	key = config.get("save_as") or "summary"

	lines, total = [], 0
	for entry in entries:
		if len(lines) < limit:
			lines.append(render(line, {**run.context, "row": entry}).strip())
		if total_field and isinstance(entry, dict):
			total += flt(entry.get(total_field))
	if len(entries) > limit:
		lines.append(_("+ {0} more").format(len(entries) - limit))

	text = separator.join(part for part in lines if part)
	if not entries:
		text = render(config.get("empty_text"), run.context) or ""
	summary = {
		"text": text,
		"count": len(entries),
		"total": flt(total, 2) if total_field else None,
		"lines": lines,
	}
	run.context.setdefault("vars", {})[key] = summary
	handle = outcome(run, node_id, "found" if entries else "empty", "found", "empty")
	return Result(handle=handle, output={"count": len(entries), "total": summary["total"]})


def addresses(text):
	return [part.strip() for part in re.split(r"[,;\s]+", text or "") if part.strip()]


def outcome(run, node_id, handle, *others):
	return handle if any(run.graph.has_output(node_id, name) for name in (handle, *others)) else None


def send_email(run, node_id, config):
	to = addresses(text_of(run, config.get("to")))
	subject = text_of(run, config.get("subject"))
	if not to or not subject:
		frappe.throw(_("Fill in who to email and the subject."))
	if not run.effect(_("Email {0}: {1}").format(", ".join(to), subject)):
		return Result()

	message = text_of(run, config.get("message"))
	frappe.sendmail(
		recipients=to,
		subject=subject,
		message=message if "<" in message else message.replace("\n", "<br>"),
		cc=addresses(text_of(run, config.get("cc"))),
		bcc=addresses(text_of(run, config.get("bcc"))),
	)
	return Result(output={"to": to, "subject": subject})


def http_request(run, node_id, config):
	import requests

	method = (config.get("method") or "GET").upper()
	url = text_of(run, config.get("url"))
	if not url.startswith(("http://", "https://")):
		frappe.throw(_("The URL must start with http:// or https://"))
	if not run.effect(_("Send a {0} request to {1}").format(method, url)):
		run.context["http"] = {"status_code": None, "response": None}
		return Result(handle=outcome(run, node_id, "done"))

	headers = {key: as_text(value) for key, value in values_of(run, config.get("headers")).items()}
	body = values_of(run, config.get("body")) or None
	response = requests.request(
		method,
		url,
		headers=headers,
		params=body if method == "GET" else None,
		json=body if method != "GET" else None,
		timeout=20,
	)
	try:
		data = response.json()
	except ValueError:
		data = response.text[:5000]
	run.context["http"] = {"status_code": response.status_code, "response": data}
	if config.get("save_as"):
		run.context.setdefault("vars", {})[config["save_as"]] = data
	if not response.ok:
		frappe.throw(_("{0} answered with status {1}").format(url, response.status_code))
	return Result(handle=outcome(run, node_id, "done"), output={"status_code": response.status_code})


def set_variable(run, node_id, config):
	from frappe.utils import now

	saved = run.context.setdefault("vars", {})
	for name, value in (config.get("variables") or {}).items():
		if name:
			saved[name] = now() if value == "{{now}}" else value_of(run, value)
	return Result(output={"saved": list(saved)})


def get_list(run, node_id, config):
	doctype = config.get("doctype")
	if not doctype:
		frappe.throw(_("Pick what to look for."))

	fields = config.get("fields") or "name"
	fields = (
		[field.strip() for field in fields.split(",") if field.strip()] if isinstance(fields, str) else fields
	)
	rows = records_of(doctype).get_all(
		doctype,
		filters=filter_values(run, config.get("filters")),
		fields=fields or ["name"],
		order_by="modified desc",
		limit=min(cint(config.get("limit")) or 20, 500),
	)
	rows = [plain(row) for row in rows]
	run.context["doc_list"] = rows
	run.context.setdefault("records", {})[config.get("save_as") or "list"] = rows
	handle = outcome(run, node_id, "found" if rows else "not_found", "found", "not_found")
	return Result(handle=handle, output={"count": len(rows)})


def apply_workflow(run, node_id, config):
	doctype = config.get("doctype")
	name = text_of(run, config.get("docname"))
	action = text_of(run, config.get("action"))
	if not doctype or not name or not action:
		frappe.throw(_("Pick the record and the workflow action."))
	if not run.effect(_("Apply {0} to {1} {2}").format(action, _(doctype), name)):
		return Result()

	from onechat.integrations.erpnext_commerce import elevated

	source = records_of(doctype)
	with elevated():
		if source.remote:
			doc = source.call(
				"frappe.model.workflow.apply_workflow", doc=source.get_doc(doctype, name), action=action
			)
		else:
			from frappe.model.workflow import apply_workflow as apply

			doc = apply(frappe.get_doc(doctype, name), action)
	state = (doc or {}).get("workflow_state")
	run.context["workflow"] = {"doctype": doctype, "docname": name, "action": action, "workflow_state": state}
	return Result(output={"workflow_state": state})


def send_notification(run, node_id, config):
	users = addresses(text_of(run, config.get("user")))
	subject = text_of(run, config.get("subject"))
	if not users or not subject:
		frappe.throw(_("Pick who to notify and the subject."))
	if not run.effect(_("Notify {0}: {1}").format(", ".join(users), subject)):
		return Result()

	for user in users:
		frappe.get_doc(
			{
				"doctype": "Notification Log",
				"subject": subject,
				"email_content": text_of(run, config.get("message")),
				"for_user": user,
				"type": "Alert",
				"document_type": config.get("reference_doctype") or None,
				"document_name": text_of(run, config.get("reference_name")) or None,
			}
		).insert(ignore_permissions=True)
	return Result(output={"notified": users})


def create_comment(run, node_id, config):
	doctype = config.get("reference_doctype")
	name = text_of(run, config.get("reference_name"))
	content = text_of(run, config.get("content"))
	if not doctype or not name or not content:
		frappe.throw(_("Pick the record and write the comment."))
	if not run.effect(_("Comment on {0} {1}").format(_(doctype), name)):
		return Result()

	comment = records_of(doctype).insert(
		{
			"doctype": "Comment",
			"comment_type": config.get("comment_type") or "Comment",
			"reference_doctype": doctype,
			"reference_name": name,
			"content": content,
		},
		ignore_permissions=True,
	)
	return Result(output={"comment": comment.get("name")})


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
	"create_from_order": create_from_order,
	"create_sales_order": create_from_order,
	"make_record": make_record,
	"submit_record": submit_record,
	"save_address": save_address,
	"send_email": send_email,
	"summarize_list": summarize_list,
	"http_request": http_request,
	"set_variable": set_variable,
	"get_list": get_list,
	"apply_workflow": apply_workflow,
	"workflow_action": apply_workflow,
	"erpnext_workflow_action": apply_workflow,
	"send_notification": send_notification,
	"create_comment": create_comment,
}

RESUME = {
	"send_buttons": resume_buttons,
	"send_list": resume_list,
	"ask_question": resume_question,
	"send_form": resume_form,
	"wait": resume_wait,
	"delay": resume_wait,
}
