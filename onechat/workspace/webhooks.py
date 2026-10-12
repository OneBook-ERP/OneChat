import ipaddress
import json
import socket
from urllib.parse import urlparse

import frappe
from frappe import _
from frappe.utils import cint

from onechat.api_types import JSON
from onechat.workspace.session import require_admin

WEBHOOK = "Webhook"
LOG = "Webhook Request Log"
CONTACT = "OneChat Contact"
MESSAGE = "OneChat Message"
CONVERSATION = "OneChat Conversation"
NOTE = "OneChat Note"
RUN = "Automation Execution Log"
BULK = "Bulk WhatsApp Message"

CONTACT_BODY = """{{
 "event": "{event}",
 "contact": {{
  "id": {{{{ doc.name | tojson }}}},
  "name": {{{{ doc.contact_name | tojson }}}},
  "channel": {{{{ (doc.channel or "WhatsApp") | tojson }}}},
  "phone": {{{{ doc.mobile_no | tojson }}}},
  "instagram_username": {{{{ doc.instagram_username | tojson }}}},
  "email": {{{{ doc.email | tojson }}}},
  "assigned_to": {{{{ doc.assigned_to | tojson }}}},
  "team": {{{{ doc.team | tojson }}}},
  "status": {{{{ doc.conversation_status | tojson }}}},
  "labels": {{{{ (doc.labels or []) | map(attribute="label") | list | tojson }}}},
  "opted_out": {{{{ (doc.opted_out or 0) | tojson }}}},
  "unread": {{{{ (doc.unread_count or 0) | tojson }}}},
  "last_message_at": {{{{ doc.last_message_at | string | tojson }}}},
  "linked_doctype": {{{{ doc.reference_doctype | tojson }}}},
  "linked_name": {{{{ doc.reference_docname | tojson }}}}
 }}
}}"""

NOTE_BODY = """{{
 "event": "{event}",
 "note": {{
  "id": {{{{ doc.name | tojson }}}},
  "contact": {{{{ doc.reference_docname | tojson }}}},
  "text": {{{{ (doc.content or "") | striptags | tojson }}}},
  "author": {{{{ doc.owner | tojson }}}},
  "created_at": {{{{ doc.creation | string | tojson }}}}
 }}
}}"""

RUN_BODY = """{{
 "event": "{event}",
 "run": {{
  "id": {{{{ doc.name | tojson }}}},
  "flow": {{{{ doc.flow | tojson }}}},
  "status": {{{{ doc.status | tojson }}}},
  "contact": {{{{ doc.contact | tojson }}}},
  "error": {{{{ doc.error_message | tojson }}}},
  "started_at": {{{{ doc.start_time | string | tojson }}}},
  "ended_at": {{{{ doc.end_time | string | tojson }}}}
 }}
}}"""

BROADCAST_BODY = """{{
 "event": "{event}",
 "broadcast": {{
  "id": {{{{ doc.name | tojson }}}},
  "title": {{{{ doc.title | tojson }}}},
  "template": {{{{ doc.template | tojson }}}},
  "recipients": {{{{ (doc.recipient_count or 0) | tojson }}}},
  "sent": {{{{ (doc.sent_count or 0) | tojson }}}},
  "skipped": {{{{ (doc.skipped_count or 0) | tojson }}}},
  "status": {{{{ doc.status | tojson }}}},
  "ab_winner": {{{{ doc.get("ab_winner") | tojson }}}}
 }}
}}"""

MESSAGE_BODY = """{{
 "event": "{event}",
 "message": {{
  "id": {{{{ doc.name | tojson }}}},
  "contact": {{{{ doc.whatsapp_contact | tojson }}}},
  "channel": {{{{ (doc.channel or "WhatsApp") | tojson }}}},
  "direction": {{{{ ("incoming" if doc.type == "Incoming" else "outgoing") | tojson }}}},
  "from": {{{{ doc.get("from") | tojson }}}},
  "to": {{{{ doc.to | tojson }}}},
  "type": {{{{ doc.content_type | tojson }}}},
  "text": {{{{ doc.message | tojson }}}},
  "template": {{{{ doc.template | tojson }}}},
  "status": {{{{ doc.status | tojson }}}},
  "source": {{{{ doc.source | tojson }}}},
  "created_at": {{{{ doc.creation | string | tojson }}}}{extra}
 }}
}}"""

FORM_EXTRA = """,
  "form": {{ doc.flow | tojson }},
  "answers": {{ doc.flow_response | tojson }}"""

CONVERSATION_BODY = """{{
 "event": "{event}",
 "conversation": {{
  "id": {{{{ doc.name | tojson }}}},
  "contact": {{{{ doc.contact | tojson }}}},
  "channel": {{{{ (doc.channel or "WhatsApp") | tojson }}}},
  "assigned_to": {{{{ doc.assigned_to | tojson }}}},
  "team": {{{{ doc.team | tojson }}}},
  "opened_at": {{{{ doc.opened_at | string | tojson }}}}
 }}
}}"""

EVENTS = {
	"chat.created": {
		"description": "A customer starts a new conversation or reopens a resolved one",
		"doctype": CONVERSATION,
		"docevent": "after_insert",
		"condition": "",
		"body": CONVERSATION_BODY,
	},
	"message.received": {
		"description": "A customer sends a message",
		"doctype": MESSAGE,
		"docevent": "after_insert",
		"condition": 'doc.type == "Incoming" and doc.content_type != "reaction"',
		"body": MESSAGE_BODY,
	},
	"message.sent": {
		"description": "An agent, bot, flow or broadcast sends a message",
		"doctype": MESSAGE,
		"docevent": "after_insert",
		"condition": 'doc.type == "Outgoing"',
		"body": MESSAGE_BODY,
	},
	"message.status": {
		"description": "A sent message is delivered, read or fails",
		"doctype": MESSAGE,
		"docevent": "on_update",
		"condition": 'doc.type == "Outgoing" and (doc.status or "").lower() in ("delivered", "read", "failed")',
		"body": MESSAGE_BODY,
	},
	"form.submitted": {
		"description": "A customer submits a WhatsApp form",
		"doctype": MESSAGE,
		"docevent": "after_insert",
		"condition": 'doc.type == "Incoming" and doc.content_type == "flow"',
		"body": MESSAGE_BODY,
		"extra": FORM_EXTRA,
	},
	"chat.assigned": {
		"description": "A conversation is assigned to someone",
		"doctype": CONTACT,
		"docevent": "on_change",
		"condition": 'doc.get("onechat_event") == "assigned"',
		"body": CONTACT_BODY,
	},
	"chat.resolved": {
		"description": "A conversation is marked resolved",
		"doctype": CONTACT,
		"docevent": "on_change",
		"condition": 'doc.get("onechat_event") == "resolved"',
		"body": CONTACT_BODY,
	},
	"contact.created": {
		"description": "A new contact is added",
		"doctype": CONTACT,
		"docevent": "after_insert",
		"condition": "",
		"body": CONTACT_BODY,
	},
	"chat.reopened": {
		"description": "A resolved conversation is opened again",
		"doctype": CONTACT,
		"docevent": "on_change",
		"condition": 'doc.get("onechat_event") == "reopened"',
		"body": CONTACT_BODY,
	},
	"chat.status_changed": {
		"description": "A conversation becomes Open, Pending or Resolved",
		"doctype": CONTACT,
		"docevent": "on_change",
		"condition": 'doc.get("onechat_event") == "status"',
		"body": CONTACT_BODY,
	},
	"chat.labels_changed": {
		"description": "Labels are added to or removed from a conversation",
		"doctype": CONTACT,
		"docevent": "on_change",
		"condition": 'doc.get("onechat_event") == "labels"',
		"body": CONTACT_BODY,
	},
	"note.added": {
		"description": "A teammate adds an internal note to a conversation",
		"doctype": NOTE,
		"docevent": "after_insert",
		"condition": 'doc.reference_doctype == "OneChat Contact"',
		"body": NOTE_BODY,
	},
	"contact.opted_out": {
		"description": "A contact stops marketing messages",
		"doctype": CONTACT,
		"docevent": "on_change",
		"condition": 'doc.get("onechat_event") == "opted_out"',
		"body": CONTACT_BODY,
	},
	"contact.opted_in": {
		"description": "A contact subscribes to marketing messages again",
		"doctype": CONTACT,
		"docevent": "on_change",
		"condition": 'doc.get("onechat_event") == "opted_in"',
		"body": CONTACT_BODY,
	},
	"flow.finished": {
		"description": "A chatbot flow run completes or fails",
		"doctype": RUN,
		"docevent": "on_update",
		"condition": 'doc.status in ("Success", "Failed")',
		"body": RUN_BODY,
	},
	"broadcast.completed": {
		"description": "A broadcast finishes sending to everyone",
		"doctype": BULK,
		"docevent": "on_change",
		"condition": 'doc.get("onechat_event") == "completed"',
		"body": BROADCAST_BODY,
	},
}

GROUPS = {
	"Conversations": (
		"chat.created",
		"chat.assigned",
		"chat.status_changed",
		"chat.resolved",
		"chat.reopened",
		"chat.labels_changed",
		"note.added",
	),
	"Messages": ("message.received", "message.sent", "message.status", "form.submitted"),
	"Contacts": ("contact.created", "contact.opted_out", "contact.opted_in"),
	"Automation": ("flow.finished", "broadcast.completed"),
}


def body_of(event):
	spec = EVENTS[event]
	return spec["body"].format(event=event, extra=spec.get("extra", ""))


def event_of(row):
	for event, spec in EVENTS.items():
		if (
			row.webhook_doctype == spec["doctype"]
			and row.webhook_docevent == spec["docevent"]
			and (row.condition or "") == spec["condition"]
		):
			return event
	return None


def fire(contact, event, doctype=CONTACT):
	if not contact or not frappe.db.exists(
		WEBHOOK, {"webhook_doctype": doctype, "webhook_docevent": "on_change", "enabled": 1}
	):
		return
	try:
		from frappe.integrations.doctype.webhook import run_webhooks

		doc = frappe.get_doc(doctype, contact)
		doc.onechat_event = event
		run_webhooks(doc, "on_change")
	except Exception:
		frappe.log_error(title=f"OneChat webhook: {event}")


def check_url(url):
	parsed = urlparse(url or "")
	if parsed.scheme not in ("http", "https") or not parsed.hostname:
		frappe.throw(_("Use a full http:// or https:// address."))
	if frappe.conf.get("onechat_allow_private_webhooks"):
		return
	try:
		addresses = {info[4][0] for info in socket.getaddrinfo(parsed.hostname, parsed.port or 443)}
	except socket.gaierror:
		frappe.throw(_("Could not find {0}.").format(parsed.hostname))
	for address in addresses:
		ip = ipaddress.ip_address(address)
		if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
			frappe.throw(_("Webhooks cannot point to private or local addresses."))


def row(doc):
	return {
		"name": doc.name,
		"event": event_of(doc),
		"url": doc.request_url,
		"enabled": cint(doc.enabled),
		"signed": cint(doc.enable_security),
		"modified": str(doc.modified),
	}


def onechat_hooks():
	doctypes = sorted({spec["doctype"] for spec in EVENTS.values()})
	rows = frappe.get_all(
		WEBHOOK,
		filters={"webhook_doctype": ["in", doctypes]},
		fields=[
			"name",
			"webhook_doctype",
			"webhook_docevent",
			"condition",
			"request_url",
			"enabled",
			"enable_security",
			"modified",
		],
		order_by="creation asc",
	)
	return [row for row in rows if event_of(row)]


@frappe.whitelist()
def catalog():
	require_admin()
	group_of = {event: group for group, events in GROUPS.items() for event in events}
	return [
		{
			"event": key,
			"description": _(spec["description"]),
			"doctype": spec["doctype"],
			"group": _(group_of.get(key, "Other")),
		}
		for group in GROUPS
		for key in GROUPS[group]
		for spec in [EVENTS[key]]
	]


@frappe.whitelist()
def webhooks():
	require_admin()
	hooks = onechat_hooks()
	last = {}
	if hooks:
		for log in frappe.get_all(
			LOG,
			filters={"webhook": ["in", [hook.name for hook in hooks]]},
			fields=["webhook", "creation", "error"],
			order_by="creation desc",
			limit_page_length=500,
		):
			last.setdefault(log.webhook, log)
	out = []
	for hook in hooks:
		entry = row(hook)
		log = last.get(hook.name)
		entry["last_sent_at"] = str(log.creation) if log else None
		entry["last_error"] = (log.error or "")[:300] if log else None
		out.append(entry)
	return out


def new_secret():
	return "whsec_" + frappe.generate_hash(length=40)


def apply(doc, event, url, enabled):
	spec = EVENTS[event]
	doc.update(
		{
			"webhook_doctype": spec["doctype"],
			"webhook_docevent": spec["docevent"],
			"condition": spec["condition"],
			"request_url": url,
			"request_method": "POST",
			"request_structure": "JSON",
			"webhook_json": body_of(event),
			"enabled": 1 if cint(enabled) else 0,
			"enable_security": 1,
		}
	)


def clean_secret(value):
	value = (value or "").strip()
	if value and len(value) < 16:
		frappe.throw(_("Use a signing secret of at least 16 characters, or leave it empty to create one."))
	return value


def hook_name(event):
	return f"OneChat · {event} · {frappe.generate_hash(length=6)}"


@frappe.whitelist(methods=["POST"])
def save(
	url: str,
	events: JSON = None,
	enabled: bool | int | str = 1,
	name: str | None = None,
	secret: str | None = None,
):
	require_admin()
	url = (url or "").strip()
	check_url(url)
	chosen = [event for event in frappe.parse_json(events) or [] if event in EVENTS]
	if not chosen:
		frappe.throw(_("Pick at least one event."))
	custom = clean_secret(secret)

	if name:
		doc = ensure_ours(name)
		apply(doc, chosen[0], url, enabled)
		if custom:
			doc.webhook_secret = custom
		doc.save(ignore_permissions=True)
		return {"webhooks": [row(doc)], "secret": None}

	secret = custom or new_secret()
	created = []
	for event in chosen:
		doc = frappe.new_doc(WEBHOOK)
		apply(doc, event, url, enabled)
		doc.webhook_secret = secret
		doc.set("__newname", hook_name(event))
		doc.insert(ignore_permissions=True)
		created.append(row(doc))
	return {"webhooks": created, "secret": None if custom else secret}


@frappe.whitelist(methods=["POST"])
def set_enabled(name: str, enabled: bool | int | str):
	require_admin()
	ensure_ours(name)
	frappe.db.set_value(WEBHOOK, name, "enabled", 1 if cint(enabled) else 0)
	frappe.cache().delete_value("webhooks")
	return True


@frappe.whitelist(methods=["POST"])
def rotate_secret(name: str):
	require_admin()
	doc = ensure_ours(name)
	secret = new_secret()
	doc.webhook_secret = secret
	doc.enable_security = 1
	doc.save(ignore_permissions=True)
	return {"secret": secret}


@frappe.whitelist(methods=["POST"])
def delete(name: str):
	require_admin()
	ensure_ours(name)
	frappe.delete_doc(WEBHOOK, name, ignore_permissions=True)
	return True


def ensure_ours(name):
	doc = frappe.get_doc(WEBHOOK, name)
	if not event_of(doc):
		frappe.throw(
			_("This webhook was not created by OneChat. Manage it from the desk."), frappe.PermissionError
		)
	return doc


@frappe.whitelist(methods=["POST"])
def test(name: str):
	require_admin()
	doc = ensure_ours(name)
	sample = frappe.get_all(doc.webhook_doctype, pluck="name", order_by="creation desc", limit_page_length=1)
	if not sample:
		frappe.throw(_("There is no {0} yet to send as a sample.").format(_(doc.webhook_doctype)))
	from frappe.integrations.doctype.webhook.webhook import enqueue_webhook

	record = frappe.get_doc(doc.webhook_doctype, sample[0])
	record.onechat_event = (event_of(doc) or "").split(".")[-1]
	enqueue_webhook(record, doc.as_dict())
	log = frappe.get_all(
		LOG,
		filters={"webhook": name},
		fields=["creation", "error", "response"],
		order_by="creation desc",
		limit_page_length=1,
	)
	result = log[0] if log else {}
	return {
		"success": not result.get("error"),
		"error": result.get("error"),
		"response": (result.get("response") or "")[:500],
	}


@frappe.whitelist()
def deliveries(name: str, limit: int | str = 50):
	require_admin()
	ensure_ours(name)
	return frappe.get_all(
		LOG,
		filters={"webhook": name},
		fields=["name", "reference_document", "url", "data", "response", "error", "creation"],
		order_by="creation desc",
		limit_page_length=min(cint(limit) or 50, 200),
	)
