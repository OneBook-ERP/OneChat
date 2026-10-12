import frappe
from frappe import _
from frappe.utils import cint, now_datetime, strip_html

from onechat.inbox.conversations import CONTACT, MESSAGE, find_contact, publish
from onechat.inbox.visibility import check as check_visible
from onechat.workspace.audit import track
from onechat.workspace.session import is_admin

STOP_WORDS = {"STOP", "UNSUBSCRIBE", "STOP ALL", "OPT OUT"}
START_WORDS = {"START", "SUBSCRIBE", "UNSTOP"}

REPLIES = {
	1: "You've been unsubscribed. Reply START to subscribe again.",
	0: "You're subscribed again. Reply STOP to unsubscribe.",
}


class OptedOutError(frappe.ValidationError):
	pass


def keyword(text):
	return " ".join(strip_html(text or "").split()).upper()


def recipient(doc):
	if doc.get("whatsapp_contact"):
		return doc.whatsapp_contact
	if doc.reference_doctype == CONTACT and doc.reference_name:
		return doc.reference_name

	return find_contact(doc.to)


def is_opted_out(number=None, contact=None):
	contact = contact or find_contact(number)
	return bool(contact and cint(frappe.db.get_value(CONTACT, contact, "opted_out")))


def is_marketing(doc):
	if doc.message_type != "Template" or not doc.template:
		return False

	return frappe.db.get_value("WhatsApp Templates", doc.template, "category") == "MARKETING"


def check_outgoing(doc, method=None):
	if doc.flags.consent_checked:
		return
	doc.flags.consent_checked = True

	if doc.type != "Outgoing" or doc.flags.consent_message or doc.content_type == "reaction":
		return

	if not (doc.bulk_message_reference or is_marketing(doc)):
		return

	if is_opted_out(contact=recipient(doc)):
		frappe.throw(
			_("This contact has opted out of marketing messages"),
			exc=OptedOutError,
			title=_("Opted out"),
		)


def on_message(doc, method=None):
	if doc.type != "Incoming" or doc.content_type != "text":
		return

	word = keyword(doc.message)
	if word in STOP_WORDS:
		value = 1
	elif word in START_WORDS:
		value = 0
	else:
		return

	doc.flags.onechat_consent_keyword = True
	try:
		contact = doc.get("whatsapp_contact") or frappe.db.get_value(MESSAGE, doc.name, "whatsapp_contact")
		if not contact:
			return

		update(contact, value)
		confirm(doc, contact, REPLIES[value])
	except Exception:
		frappe.log_error(title="OneChat opt-out")


def update(contact, value):
	previous = frappe.db.get_value(CONTACT, contact, "opted_out")
	track(CONTACT, contact, [("opted_out", cint(previous), value)])
	frappe.db.set_value(
		CONTACT,
		contact,
		{"opted_out": value, "opted_out_at": now_datetime() if value else None},
		update_modified=False,
	)
	publish(contact)
	if cint(previous) != cint(value):
		from onechat.workspace.webhooks import fire

		fire(contact, "opted_out" if value else "opted_in")


def confirm(doc, contact, text):
	reply = frappe.new_doc(MESSAGE)
	reply.update(
		{
			"type": "Outgoing",
			"message_type": "Manual",
			"source": "Auto reply",
			"content_type": "text",
			"to": doc.get("from"),
			"message": _(text),
			"whatsapp_account": doc.whatsapp_account,
			"reference_doctype": CONTACT,
			"reference_name": contact,
		}
	)
	reply.flags.consent_message = True
	reply.insert(ignore_permissions=True)


@frappe.whitelist()
def set_opted_out(contact: str, opted_out: int | str):
	check_visible(contact)
	if not is_admin():
		frappe.throw(_("Only OneChat admins can change marketing consent"), frappe.PermissionError)

	value = 1 if cint(opted_out) else 0
	update(contact, value)

	return frappe.db.get_value(CONTACT, contact, ["name", "opted_out", "opted_out_at"], as_dict=True)
