import re

import frappe
from frappe import _
from frappe.utils import cint, now_datetime, strip_html

from onechat.inbox.routing import config, is_open
from onechat.onechat.doctype.onechat_auto_reply.onechat_auto_reply import keyword_list
from onechat.onechat.doctype.onechat_media.onechat_media import media_type_of
from onechat.workspace.session import is_admin

RULE = "OneChat Auto Reply"
CONTACT = "OneChat Contact"
MESSAGE = "OneChat Message"
TEXT_TYPES = ("text", "button", "interactive")


def on_message(doc, method=None):
	if (
		doc.type != "Incoming"
		or doc.content_type not in TEXT_TYPES
		or doc.flags.get("onechat_flow_handled")
		or doc.flags.get("onechat_survey")
	):
		return

	contact = doc.get("whatsapp_contact") or (
		doc.reference_name if doc.reference_doctype == CONTACT else None
	)
	text = normalize(strip_html(doc.message or ""))
	if not contact or not text:
		return

	frappe.db.savepoint("onechat_auto_reply")
	try:
		rule = first_match(text, contact)
		if rule:
			reply(doc, contact, rule)
			doc.flags.onechat_auto_replied = True
	except Exception:
		frappe.db.rollback(save_point="onechat_auto_reply")
		frappe.log_error(title="OneChat auto reply", reference_doctype=MESSAGE, reference_name=doc.name)


def normalize(value):
	return " ".join((value or "").split()).lower()


def matches(text, keyword, match_type):
	if match_type == "Exact":
		return text.strip(" .,!?¿¡") == keyword
	if match_type == "Starts with":
		return re.match(rf"{re.escape(keyword)}(?!\w)", text) is not None

	return re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", text) is not None


def first_match(text, contact):
	rules = frappe.get_all(
		RULE,
		filters={"enabled": 1},
		fields=["name", "match_type", "keywords", "active_when", "cooldown_minutes", "message", "attach"],
		order_by="priority desc, creation asc",
	)
	if not rules:
		return None

	hours_open = None
	for rule in rules:
		if not any(matches(text, keyword, rule.match_type) for keyword in keyword_list(rule.keywords)):
			continue

		if rule.active_when != "Always":
			if hours_open is None:
				hours_open = business_open()
			if hours_open != (rule.active_when == "During business hours"):
				continue

		return None if cooling(rule, contact) else rule

	return None


def business_open():
	settings = config()
	return not cint(settings.business_hours_enabled) or is_open(settings, now_datetime())


def cooling(rule, contact):
	minutes = cint(rule.cooldown_minutes)
	if minutes <= 0:
		return False

	key = f"onechat:auto-reply:{rule.name}:{contact}"
	cache = frappe.cache()
	if cache.get_value(key):
		return True

	cache.set_value(key, 1, expires_in_sec=minutes * 60)
	return False


def personalize(text, contact):
	name = (frappe.db.get_value(CONTACT, contact, "contact_name") or "").strip()
	return text.replace("{{name}}", name).replace("{{first_name}}", name.split(" ")[0] if name else "")


def reply(doc, contact, rule):
	mobile = frappe.db.get_value(CONTACT, contact, "mobile_no") or doc.get("from")
	if not mobile:
		return

	outgoing = frappe.new_doc(MESSAGE)
	outgoing.update(
		{
			"type": "Outgoing",
			"message_type": "Manual",
			"source": "Auto reply",
			"content_type": media_type_of(rule.attach) if rule.attach else "text",
			"message": personalize(rule.message or "", contact),
			"attach": rule.attach,
			"to": mobile,
			"reference_doctype": CONTACT,
			"reference_name": contact,
			"whatsapp_account": doc.get("whatsapp_account"),
		}
	)
	outgoing.insert(ignore_permissions=True)

	frappe.db.set_value(
		RULE,
		rule.name,
		{
			"reply_count": (frappe.db.get_value(RULE, rule.name, "reply_count") or 0) + 1,
			"last_replied_at": now_datetime(),
		},
		update_modified=False,
	)


@frappe.whitelist()
def test(text: str):
	if not is_admin():
		frappe.throw(_("Only OneChat admins can test auto replies."), frappe.PermissionError)

	text = normalize(text)
	for rule in frappe.get_all(
		RULE,
		filters={"enabled": 1},
		fields=["name", "rule_name", "match_type", "keywords", "active_when"],
		order_by="priority desc, creation asc",
	):
		for keyword in keyword_list(rule.keywords):
			if matches(text, keyword, rule.match_type):
				return {
					"name": rule.name,
					"rule_name": rule.rule_name,
					"keyword": keyword,
					"active_when": rule.active_when,
				}

	return None
