import frappe
from frappe.utils import cint, now_datetime, time_diff_in_seconds

CONTACT = "OneChat Contact"
CONVERSATION = "OneChat Conversation"
AUTOMATED = ("Bot", "Auto reply", "Away message")


def current(contact):
	return frappe.db.get_value(
		CONVERSATION, {"contact": contact, "status": "Open"}, "name", order_by="opened_at desc"
	)


def ownership(contact):
	return frappe.db.get_value(CONTACT, contact, ["assigned_to", "team"], as_dict=True) or {}


def seconds_between(start, end):
	return max(0, cint(time_diff_in_seconds(end, start))) if start and end else 0


def open_conversation(contact, message):
	owner = ownership(contact)
	doc = frappe.get_doc(
		{
			"doctype": CONVERSATION,
			"contact": contact,
			"status": "Open",
			"whatsapp_account": message.get("whatsapp_account"),
			"opened_at": message.creation or now_datetime(),
			"assigned_to": owner.get("assigned_to"),
			"team": owner.get("team"),
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def bump(name, field, values=None):
	count = cint(frappe.db.get_value(CONVERSATION, name, field)) + 1
	frappe.db.set_value(CONVERSATION, name, {field: count, **(values or {})}, update_modified=False)


def on_message(doc, contact):
	if doc.content_type == "reaction":
		return

	if doc.type == "Incoming":
		bump(current(contact) or open_conversation(contact, doc), "incoming_count")
		return

	name = current(contact)
	if not name:
		return

	if doc.get("source") == "Agent":
		responded(name, contact, doc)
	elif doc.get("source") in AUTOMATED:
		bump(name, "bot_replies")


def responded(name, contact, doc):
	row = frappe.db.get_value(CONVERSATION, name, ["opened_at", "first_response_at"], as_dict=True)
	values = {**ownership(contact)}
	if not row.first_response_at:
		at = doc.creation or now_datetime()
		values.update(
			{
				"first_response_at": at,
				"first_response_by": doc.owner or frappe.session.user,
				"response_seconds": seconds_between(row.opened_at, at),
			}
		)
	bump(name, "agent_replies", values)


def bot_started(contact, flow):
	name = current(contact)
	if name and not frappe.db.get_value(CONVERSATION, name, "bot_flow"):
		frappe.db.set_value(CONVERSATION, name, "bot_flow", flow, update_modified=False)


def resolved(contact, user=None):
	from onechat.inbox.routing import release
	from onechat.inbox.service import stop_clock

	name = current(contact)
	if name:
		close(name, contact, user)
	stop_clock(contact)
	release(contact)
	from onechat.workspace.webhooks import fire

	fire(contact, "resolved")


def close(name, contact, user):
	at = now_datetime()
	opened_at = frappe.db.get_value(CONVERSATION, name, "opened_at")
	frappe.db.set_value(
		CONVERSATION,
		name,
		{
			**ownership(contact),
			"status": "Resolved",
			"resolved_at": at,
			"resolved_by": user,
			"resolution_seconds": seconds_between(opened_at, at),
		},
		update_modified=False,
	)
