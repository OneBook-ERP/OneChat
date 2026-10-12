import frappe
from frappe import _
from frappe.utils import add_to_date, cint, get_datetime, get_fullname, now_datetime

from onechat.inbox.conversations import CONTACT, MESSAGE, guard, publish
from onechat.inbox.visibility import check as check_visible
from onechat.workspace.audit import track
from onechat.workspace.session import is_admin, require

REMINDER = "OneChat Reminder"
MAX_DAYS = 365
BATCH = 200


def future(value):
	moment = get_datetime(value) if value else None
	now = now_datetime()
	if not moment or moment <= now:
		frappe.throw(_("Pick a time in the future."))
	if moment > add_to_date(now, days=MAX_DAYS):
		frappe.throw(_("Pick a time within the next year."))
	return moment


def contact_title(contact):
	row = frappe.db.get_value(CONTACT, contact, ["contact_name", "mobile_no"], as_dict=True) or {}
	return row.get("contact_name") or row.get("mobile_no") or contact


def alert(user, contact, kind, text, reminder=None):
	title = contact_title(contact)
	subject = _("{0}: {1}").format(title, text)
	frappe.get_doc(
		{
			"doctype": "Notification Log",
			"subject": subject,
			"for_user": user,
			"type": "Alert",
			"document_type": CONTACT,
			"document_name": contact,
		}
	).insert(ignore_permissions=True)
	frappe.publish_realtime(
		"onechat_reminder",
		{"contact": contact, "contact_name": title, "kind": kind, "text": text, "reminder": reminder},
		user=user,
		after_commit=True,
	)


@frappe.whitelist()
def snooze(contact: str, until: str):
	guard()
	require(CONTACT, "write")
	check_visible(contact)
	moment = future(until)
	previous = frappe.db.get_value(CONTACT, contact, "snoozed_until")
	frappe.db.set_value(
		CONTACT, contact, {"snoozed_until": moment, "snoozed_by": frappe.session.user}, update_modified=False
	)
	track(CONTACT, contact, [("snoozed_until", previous, moment)])
	publish(contact)
	return str(moment)


@frappe.whitelist()
def unsnooze(contact: str):
	guard()
	require(CONTACT, "write")
	check_visible(contact)
	wake(contact, notify=False)


def wake(contact, notify=True, reason=None):
	row = frappe.db.get_value(CONTACT, contact, ["snoozed_until", "snoozed_by"], as_dict=True)
	if not row or not row.snoozed_until:
		return
	frappe.db.set_value(CONTACT, contact, {"snoozed_until": None, "snoozed_by": None}, update_modified=False)
	track(CONTACT, contact, [("snoozed_until", row.snoozed_until, None)])
	if notify and row.snoozed_by:
		alert(row.snoozed_by, contact, "snooze", reason or _("Snooze ended, the chat is back in your inbox"))
	publish(contact)


def reminder_row(doc):
	return {
		"name": doc.name,
		"contact": doc.contact,
		"user": doc.user,
		"user_name": get_fullname(doc.user),
		"remind_at": str(doc.remind_at),
		"only_if_no_reply": cint(doc.only_if_no_reply),
		"note": doc.note,
		"status": doc.status,
		"owner": doc.owner,
	}


@frappe.whitelist()
def add_reminder(
	contact: str,
	remind_at: str,
	only_if_no_reply: bool | int | str = 1,
	note: str | None = None,
	user: str | None = None,
):
	guard()
	check_visible(contact)
	user = user or frappe.session.user
	if user != frappe.session.user and not is_admin():
		frappe.throw(_("You can only set reminders for yourself."), frappe.PermissionError)
	doc = frappe.get_doc(
		{
			"doctype": REMINDER,
			"contact": contact,
			"user": user,
			"remind_at": future(remind_at),
			"only_if_no_reply": 1 if cint(only_if_no_reply) else 0,
			"note": (note or "").strip() or None,
			"status": "Pending",
		}
	).insert(ignore_permissions=True)
	return reminder_row(doc)


@frappe.whitelist()
def cancel_reminder(name: str):
	guard()
	doc = frappe.get_doc(REMINDER, name)
	check_visible(doc.contact)
	if frappe.session.user not in (doc.user, doc.owner) and not is_admin():
		frappe.throw(
			_("Only the person it is for, whoever set it, or an admin can cancel this reminder."),
			frappe.PermissionError,
		)
	if doc.status == "Pending":
		doc.db_set("status", "Cancelled")
	return reminder_row(doc)


@frappe.whitelist()
def reminders(contact: str):
	guard()
	check_visible(contact)
	return [
		reminder_row(doc)
		for doc in frappe.get_all(
			REMINDER,
			filters={"contact": contact, "status": "Pending"},
			fields=["name", "contact", "user", "remind_at", "only_if_no_reply", "note", "status", "owner"],
			order_by="remind_at asc",
		)
	]


def pending_contacts(user):
	return frappe.get_all(
		REMINDER, filters={"user": user, "status": "Pending"}, pluck="contact", distinct=True
	)


def replied_since(contact, since):
	return bool(
		frappe.get_all(
			MESSAGE,
			filters={
				"whatsapp_contact": contact,
				"type": "Incoming",
				"content_type": ["!=", "reaction"],
				"creation": [">", since],
			},
			pluck="name",
			limit_page_length=1,
		)
	)


def run():
	now = now_datetime()
	for contact in frappe.get_all(
		CONTACT, filters={"snoozed_until": ["<=", now]}, pluck="name", limit_page_length=BATCH
	):
		try:
			wake(contact)
		except Exception:
			frappe.log_error(title=f"OneChat snooze: {contact}")

	for row in frappe.get_all(
		REMINDER,
		filters={"status": "Pending", "remind_at": ["<=", now]},
		fields=["name", "contact", "user", "note", "only_if_no_reply", "creation"],
		order_by="remind_at asc",
		limit_page_length=BATCH,
	):
		try:
			if cint(row.only_if_no_reply) and replied_since(row.contact, row.creation):
				frappe.db.set_value(REMINDER, row.name, "status", "Skipped", update_modified=False)
				continue
			text = row.note or (
				_("No reply yet, time to follow up") if cint(row.only_if_no_reply) else _("Time to follow up")
			)
			alert(row.user, row.contact, "reminder", text, row.name)
			frappe.db.set_value(REMINDER, row.name, {"status": "Sent", "sent_at": now}, update_modified=False)
		except Exception:
			frappe.log_error(title=f"OneChat reminder: {row.name}")


def on_incoming(doc, contact):
	if doc.type != "Incoming" or doc.content_type == "reaction":
		return
	if frappe.db.get_value(CONTACT, contact, "snoozed_until"):
		wake(contact, reason=_("The customer replied, so the snooze ended"))
	reminder = frappe.qb.DocType(REMINDER)
	(
		frappe.qb.update(reminder)
		.set(reminder.status, "Skipped")
		.where(
			(reminder.contact == contact) & (reminder.status == "Pending") & (reminder.only_if_no_reply == 1)
		)
		.run()
	)
