import frappe
from frappe.utils import cint

from onechat.inbox.auto_reply import personalize
from onechat.inbox.conversations import CONTACT, MESSAGE
from onechat.instagram.comments import settings


def thank(message):
	config = settings()
	if not cint(config.ig_story_thanks) or not (config.ig_story_thanks_message or "").strip():
		return
	doc = frappe.get_doc(MESSAGE, message)
	contact = doc.get("whatsapp_contact")
	if not contact:
		return
	key = f"onechat:story_thanks:{contact}"
	cache = frappe.cache()
	if cache.get_value(key):
		return
	cache.set_value(key, 1, expires_in_sec=max(cint(config.ig_story_thanks_hours), 1) * 3600)

	frappe.get_doc(
		{
			"doctype": MESSAGE,
			"type": "Outgoing",
			"message_type": "Manual",
			"source": "Auto reply",
			"content_type": "text",
			"message": personalize(config.ig_story_thanks_message, contact),
			"to": doc.get("from"),
			"reference_doctype": CONTACT,
			"reference_name": contact,
			"whatsapp_contact": contact,
			"whatsapp_account": doc.whatsapp_account,
		}
	).insert(ignore_permissions=True)
