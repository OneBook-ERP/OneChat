import json

import frappe
from frappe.utils import add_days, get_datetime, now_datetime, time_diff_in_seconds

CONTACT = "OneChat Contact"
MESSAGE = "OneChat Message"
CONVERSATION = "OneChat Conversation"
DAYS = 90
AUTOMATED = ("Bot", "Auto reply", "Away message")


def execute():
	tag_sources()
	if not frappe.db.count(CONVERSATION):
		rebuild_conversations()


def tag_sources():
	message = frappe.qb.DocType(MESSAGE)
	blank = message.source.isnull() | (message.source == "")
	(
		frappe.qb.update(message)
		.set(message.source, "Broadcast")
		.where(blank & message.bulk_message_reference.isnotnull() & (message.bulk_message_reference != ""))
	).run()

	agents = [
		user
		for user in frappe.get_all("OneChat User", pluck="user")
		if user and user not in ("Administrator", "Guest")
	]
	if agents:
		(
			frappe.qb.update(message)
			.set(message.source, "Agent")
			.where(
				blank
				& (message.type == "Outgoing")
				& message.owner.isin(agents)
				& (message.content_type != "reaction")
				& (message.whatsapp_contact.isnotnull())
			)
		).run()


def resolutions(since):
	out = {}
	for row in frappe.get_all(
		"Version",
		filters={
			"ref_doctype": CONTACT,
			"creation": [">=", since],
			"data": ["like", "%conversation_status%"],
		},
		fields=["docname", "owner", "creation", "data"],
		order_by="creation asc",
	):
		try:
			changed = json.loads(row.data).get("changed") or []
		except ValueError:
			continue
		if any(field == "conversation_status" and new == "Resolved" for field, old, new in changed):
			out.setdefault(row.docname, []).append(("resolved", row.creation, row.owner))

	return out


def rebuild_conversations():
	since = add_days(now_datetime(), -DAYS)
	events = resolutions(since)
	for row in frappe.get_all(
		MESSAGE,
		filters={
			"creation": [">=", since],
			"whatsapp_contact": ["is", "set"],
			"content_type": ["!=", "reaction"],
		},
		fields=["whatsapp_contact", "type", "source", "owner", "creation", "whatsapp_account"],
		order_by="creation asc",
	):
		kind = (
			"in"
			if row.type == "Incoming"
			else "agent"
			if row.source == "Agent"
			else "bot"
			if row.source in AUTOMATED
			else None
		)
		if kind:
			events.setdefault(row.whatsapp_contact, []).append(
				(kind, row.creation, row.owner, row.whatsapp_account)
			)

	contacts = (
		{
			row.name: row
			for row in frappe.get_all(
				CONTACT,
				filters={"name": ["in", list(events)]},
				fields=["name", "conversation_status", "resolved_at", "resolved_by", "assigned_to", "team"],
			)
		}
		if events
		else {}
	)

	for contact, rows in events.items():
		if contact in contacts:
			replay(contacts[contact], sorted(rows, key=lambda event: get_datetime(event[1])))


def replay(contact, events):
	current = None
	for event in events:
		kind, at, user = event[0], event[1], event[2]
		if kind == "in":
			if not current:
				current = {
					"opened_at": at,
					"whatsapp_account": event[3],
					"incoming_count": 0,
					"agent_replies": 0,
					"bot_replies": 0,
				}
			current["incoming_count"] += 1
		elif not current:
			continue
		elif kind == "agent":
			current["agent_replies"] += 1
			if not current.get("first_response_at"):
				current.update(
					first_response_at=at,
					first_response_by=user,
					response_seconds=seconds(current["opened_at"], at),
				)
		elif kind == "bot":
			current["bot_replies"] += 1
		elif kind == "resolved":
			save(contact, current, at, user)
			current = None

	if current:
		if contact.conversation_status == "Resolved":
			save(contact, current, contact.resolved_at or events[-1][1], contact.resolved_by)
		else:
			save(contact, current)


def seconds(start, end):
	return max(0, int(time_diff_in_seconds(end, start)))


def save(contact, values, resolved_at=None, resolved_by=None):
	if resolved_at:
		values.update(
			status="Resolved",
			resolved_at=resolved_at,
			resolved_by=resolved_by,
			resolution_seconds=seconds(values["opened_at"], resolved_at),
		)
	frappe.get_doc(
		{
			"doctype": CONVERSATION,
			"contact": contact.name,
			"status": "Open",
			"assigned_to": contact.assigned_to,
			"team": contact.team,
			**values,
		}
	).insert(ignore_permissions=True)
