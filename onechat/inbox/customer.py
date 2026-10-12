import json
import re

import frappe
from frappe import _
from frappe.query_builder import Order
from frappe.query_builder.functions import Count
from frappe.utils import cint, get_datetime, get_fullname, strip_html

from onechat import integrations
from onechat.api_types import JSON
from onechat.inbox.conversations import CONTACT, MESSAGE, NOTE, contact_labels, guard
from onechat.inbox.scores import summary as score_summary
from onechat.inbox.scores import update_contact
from onechat.inbox.visibility import check as check_visible

CONVERSATION = "OneChat Conversation"
SESSION = "OneChat Flow Session"
PAGE = 30
REF = re.compile(r"\[ref:([A-Za-z0-9]{4,12})\]")
KINDS = ("conversation", "note", "campaign", "form", "flow", "link", "consent", "record")
PROFILE_FIELDS = [
	"name",
	"contact_name",
	"mobile_no",
	"email",
	"channel",
	"instagram_username",
	"profile_image",
	"reference_doctype",
	"reference_docname",
	"assigned_to",
	"team",
	"conversation_status",
	"opted_out",
	"opted_out_at",
	"last_message_at",
	"creation",
]


def stamp(value):
	return str(get_datetime(value)) if value else None


def excerpt(text, size=140):
	text = " ".join(strip_html(text or "").split())
	return text if len(text) <= size else f"{text[: size - 1]}…"


def duration(seconds):
	seconds = cint(seconds)
	if not seconds:
		return None
	if seconds < 60:
		return _("{0}s").format(seconds)
	minutes = round(seconds / 60)
	if minutes < 60:
		return _("{0}m").format(minutes)
	hours = minutes // 60
	if hours < 24:
		return _("{0}h {1}m").format(hours, minutes % 60) if minutes % 60 else _("{0}h").format(hours)
	return _("{0}d").format(hours // 24)


def before_filter(field, before):
	return {field: ["<", before]} if before else {}


def conversation_events(contact, before, limit):
	rows = frappe.get_all(
		CONVERSATION,
		filters={"contact": contact, **before_filter("opened_at", before)},
		fields=[
			"name",
			"status",
			"opened_at",
			"incoming_count",
			"agent_replies",
			"bot_replies",
			"first_response_by",
			"response_seconds",
			"resolved_by",
			"resolution_seconds",
			"bot_flow",
		],
		order_by="opened_at desc",
		limit_page_length=limit,
	)
	out = []
	for row in rows:
		parts = [_("{0} messages from the customer").format(cint(row.incoming_count))]
		if row.first_response_by:
			reply = duration(row.response_seconds)
			parts.append(
				_("first reply by {0} in {1}").format(get_fullname(row.first_response_by), reply)
				if reply
				else _("first reply by {0}").format(get_fullname(row.first_response_by))
			)
		elif row.bot_flow:
			parts.append(_("handled by {0}").format(row.bot_flow))
		if row.status == "Resolved" and row.resolved_by:
			parts.append(_("resolved by {0}").format(get_fullname(row.resolved_by)))
		out.append(
			{
				"id": f"conversation:{row.name}",
				"kind": "conversation",
				"at": stamp(row.opened_at),
				"title": _("Conversation resolved") if row.status == "Resolved" else _("Conversation open"),
				"subtitle": " · ".join(parts),
				"status": _(row.status),
				"theme": "green" if row.status == "Resolved" else "blue",
				"route": {"name": "Inbox", "params": {"contact": contact}},
			}
		)
	return out


def note_events(contact, before, limit):
	rows = frappe.get_all(
		NOTE,
		filters={
			"reference_doctype": CONTACT,
			"reference_docname": contact,
			**before_filter("creation", before),
		},
		fields=["name", "title", "content", "owner", "creation"],
		order_by="creation desc",
		limit_page_length=limit,
	)
	return [
		{
			"id": f"note:{row.name}",
			"kind": "note",
			"at": stamp(row.creation),
			"title": _("Note by {0}").format(get_fullname(row.owner)),
			"text": excerpt(row.content, 240),
			"route": {"name": "Inbox", "params": {"contact": contact}},
		}
		for row in rows
	]


def campaign_events(contact, before, limit):
	message = frappe.qb.DocType(MESSAGE)
	query = (
		frappe.qb.from_(message)
		.select(
			message.name,
			message.creation,
			message.template,
			message.status,
			message.source,
			message.bulk_message_reference,
		)
		.where(
			(message.whatsapp_contact == contact)
			& (message.type == "Outgoing")
			& (message.source.isin(["Broadcast", "Notification"]) | (message.message_type == "Template"))
		)
		.orderby(message.creation, order=Order.desc)
		.limit(limit)
	)
	if before:
		query = query.where(message.creation < before)
	rows = query.run(as_dict=True)

	broadcasts = {row.bulk_message_reference for row in rows if row.bulk_message_reference}
	titles = (
		dict(
			frappe.get_all(
				"Bulk WhatsApp Message",
				filters={"name": ["in", list(broadcasts)]},
				fields=["name", "title"],
				as_list=True,
			)
		)
		if broadcasts
		else {}
	)
	templates = {row.template for row in rows if row.template}
	names = (
		dict(
			frappe.get_all(
				"WhatsApp Templates",
				filters={"name": ["in", list(templates)]},
				fields=["name", "template_name"],
				as_list=True,
			)
		)
		if templates
		else {}
	)

	out = []
	for row in rows:
		template = names.get(row.template) or row.template or _("a message")
		if row.bulk_message_reference:
			title = _("Received broadcast {0}").format(
				titles.get(row.bulk_message_reference) or row.bulk_message_reference
			)
		elif row.source == "Notification":
			title = _("Sent notification {0}").format(template)
		else:
			title = _("Sent template {0}").format(template)
		status = (row.status or "").lower()
		out.append(
			{
				"id": f"campaign:{row.name}",
				"kind": "campaign",
				"at": stamp(row.creation),
				"title": title,
				"subtitle": template if row.bulk_message_reference else None,
				"status": _(status.capitalize()) if status else None,
				"theme": {"read": "green", "delivered": "blue", "failed": "red"}.get(status, "gray"),
			}
		)
	return out


def form_events(contact, before, limit):
	rows = frappe.get_all(
		MESSAGE,
		filters={
			"whatsapp_contact": contact,
			"type": "Incoming",
			"content_type": "flow",
			**before_filter("creation", before),
		},
		fields=["name", "creation", "flow", "message"],
		order_by="creation desc",
		limit_page_length=limit,
	)
	forms = {row.flow for row in rows if row.flow}
	names = (
		dict(
			frappe.get_all(
				"WhatsApp Flow",
				filters={"name": ["in", list(forms)]},
				fields=["name", "flow_name"],
				as_list=True,
			)
		)
		if forms
		else {}
	)
	return [
		{
			"id": f"form:{row.name}",
			"kind": "form",
			"at": stamp(row.creation),
			"title": _("Submitted form {0}").format(names.get(row.flow) or row.flow or _("form")),
			"text": excerpt(row.message, 180),
			"route": {"name": "FormBuilder", "params": {"name": row.flow}} if row.flow else None,
		}
		for row in rows
	]


def flow_events(contact, before, limit):
	rows = frappe.get_all(
		SESSION,
		filters={"contact": contact, **before_filter("creation", before)},
		fields=["name", "creation", "flow", "status", "stop_reason"],
		order_by="creation desc",
		limit_page_length=limit,
	)
	flows = {row.flow for row in rows}
	names = (
		dict(
			frappe.get_all(
				"Automation Flow",
				filters={"name": ["in", list(flows)]},
				fields=["name", "flow_name"],
				as_list=True,
			)
		)
		if flows
		else {}
	)
	themes = {
		"Completed": "green",
		"Waiting": "blue",
		"Running": "blue",
		"Stopped": "gray",
		"Expired": "amber",
		"Failed": "red",
	}
	return [
		{
			"id": f"flow:{row.name}",
			"kind": "flow",
			"at": stamp(row.creation),
			"title": _("Chatbot: {0}").format(names.get(row.flow) or row.flow),
			"subtitle": row.stop_reason,
			"status": _(row.status),
			"theme": themes.get(row.status, "gray"),
			"route": {"name": "FlowBuilder", "params": {"name": row.flow}},
		}
		for row in rows
	]


def link_events(contact, before, limit):
	rows = frappe.get_all(
		MESSAGE,
		filters={
			"whatsapp_contact": contact,
			"type": "Incoming",
			"message": ["like", "%[ref:%"],
			**before_filter("creation", before),
		},
		fields=["name", "creation", "message"],
		order_by="creation desc",
		limit_page_length=limit,
	)
	codes = {match.group(1).upper() for row in rows for match in [REF.search(row.message or "")] if match}
	titles = (
		{
			row.ref_code: row.title
			for row in frappe.get_all(
				"OneChat Chat Link", filters={"ref_code": ["in", list(codes)]}, fields=["ref_code", "title"]
			)
		}
		if codes
		else {}
	)
	out = []
	for row in rows:
		match = REF.search(row.message or "")
		if not match:
			continue
		code = match.group(1).upper()
		out.append(
			{
				"id": f"link:{row.name}",
				"kind": "link",
				"at": stamp(row.creation),
				"title": _("Came from chat link {0}").format(titles.get(code) or code),
			}
		)
	return out


def consent_events(contact, before, limit):
	rows = frappe.get_all(
		"Version",
		filters={
			"ref_doctype": CONTACT,
			"docname": contact,
			"data": ["like", "%opted_out%"],
			**before_filter("creation", before),
		},
		fields=["name", "creation", "owner", "data"],
		order_by="creation desc",
		limit_page_length=limit,
	)
	out = []
	for row in rows:
		try:
			changed = json.loads(row.data).get("changed") or []
		except ValueError:
			continue
		for field, old, new in changed:
			if field != "opted_out":
				continue
			opted_out = cint(new)
			out.append(
				{
					"id": f"consent:{row.name}",
					"kind": "consent",
					"at": stamp(row.creation),
					"title": _("Opted out of marketing") if opted_out else _("Opted back in to marketing"),
					"subtitle": None
					if row.owner in ("Guest", "Administrator")
					else _("by {0}").format(get_fullname(row.owner)),
					"theme": "red" if opted_out else "green",
				}
			)
	return out


SOURCES = {
	"conversation": conversation_events,
	"note": note_events,
	"campaign": campaign_events,
	"form": form_events,
	"flow": flow_events,
	"link": link_events,
	"consent": consent_events,
}


def record_events(contact, before, limit):
	rows = [
		{**row, "kind": "record", "at": stamp(row.get("at"))}
		for row in integrations.record_timeline(contact, before, limit)
	]
	return [row for row in rows if row["at"] and (not before or row["at"] < before)]


@frappe.whitelist()
def timeline(contact: str, before: str | None = None, kinds: JSON = None, limit: int | str = PAGE):
	guard()
	check_visible(contact)
	if not frappe.db.exists(CONTACT, contact):
		frappe.throw(_("Contact not found."))

	limit = min(cint(limit) or PAGE, 100)
	wanted = [kind for kind in (frappe.parse_json(kinds) if kinds else KINDS) if kind in KINDS]
	events = []
	for kind in wanted:
		fetch = record_events if kind == "record" else SOURCES[kind]
		try:
			events += fetch(contact, before, limit)
		except Exception:
			frappe.log_error(title=f"OneChat timeline: {kind}")

	events = sorted(
		(event for event in events if event.get("at")), key=lambda event: event["at"], reverse=True
	)[:limit]
	return {"events": events, "cursor": events[-1]["at"] if len(events) == limit else None}


def scores(contact):
	if not frappe.get_meta(CONTACT).has_field("value_group"):
		return {}
	summary = score_summary(contact)
	if not summary.get("scores_updated_at"):
		try:
			update_contact(contact)
			summary = score_summary(contact)
		except Exception:
			frappe.log_error(title="OneChat customer scores")
	return summary


@frappe.whitelist()
def profile(contact: str):
	guard()
	check_visible(contact)
	row = frappe.db.get_value(CONTACT, contact, PROFILE_FIELDS, as_dict=True)
	if not row:
		frappe.throw(_("Contact not found."))

	conversation = frappe.qb.DocType(CONVERSATION)
	count = (
		frappe.qb.from_(conversation).select(Count("*")).where(conversation.contact == contact).run()[0][0]
	)
	stats = [
		{"key": "conversations", "label": _("Conversations"), "value": cint(count)},
		{"key": "first_seen", "label": _("Customer since"), "value": stamp(row.creation), "type": "date"},
		{
			"key": "last_contact",
			"label": _("Last message"),
			"value": stamp(row.last_message_at),
			"type": "ago",
		},
	]
	return {
		**row,
		"creation": stamp(row.creation),
		"last_message_at": stamp(row.last_message_at),
		"opted_out_at": stamp(row.opted_out_at),
		"labels": contact_labels(contact),
		"assigned_name": get_fullname(row.assigned_to) if row.assigned_to else None,
		"stats": stats,
		"record_stats": integrations.record_stats(contact),
		"scores": scores(contact),
	}
