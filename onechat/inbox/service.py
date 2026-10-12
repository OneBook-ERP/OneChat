import json
from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import add_to_date, cint, get_datetime, now_datetime

CONTACT = "OneChat Contact"
MESSAGE = "OneChat Message"
CONVERSATION = "OneChat Conversation"
SURVEY_PREFIX = "csat_"
SURVEY_WINDOW_HOURS = 48
REPLY_WINDOW_HOURS = 24
BUSINESS_DAYS_AHEAD = 14
RATINGS = ((3, "Great"), (2, "Okay"), (1, "Poor"))
RATING_ICONS = {3: "😀", 2: "😐", 1: "😞"}


def settings():
	from onechat.inbox.routing import config

	return config()


def business_due(config, start, minutes):
	from onechat.inbox.routing import ranges

	days = ranges(config)
	if not cint(config.get("business_hours_enabled")) or not days:
		return add_to_date(start, minutes=minutes)
	left = minutes
	moment = start
	for offset in range(BUSINESS_DAYS_AHEAD):
		day = (start + timedelta(days=offset)).replace(hour=0, minute=0, second=0, microsecond=0)
		for begin, end in sorted(days.get(day.weekday(), [])):
			window_start = max(day + timedelta(minutes=begin), moment)
			window_end = day + timedelta(minutes=end)
			if window_end <= window_start:
				continue
			available = (window_end - window_start).total_seconds() / 60
			if available >= left:
				return window_start + timedelta(minutes=left)
			left -= available
	return add_to_date(start, minutes=minutes)


def due_time(config, start):
	minutes = max(cint(config.get("sla_first_response_minutes")) or 30, 1)
	if cint(config.get("sla_business_hours_only")):
		return business_due(config, get_datetime(start), minutes)
	return add_to_date(get_datetime(start), minutes=minutes)


ANSWERS = ("Agent", "Bot")
NO_REPLY_NEEDED = ("flow", "reaction")


def needs_reply(doc):
	return doc.get("content_type") not in NO_REPLY_NEEDED and not doc.flags.get("onechat_survey")


def start_clock(contact, at):
	config = settings()
	if not cint(config.get("sla_enabled")):
		return
	if frappe.db.get_value(CONTACT, contact, "sla_due_at"):
		return
	frappe.db.set_value(
		CONTACT, contact, {"sla_due_at": due_time(config, at), "sla_breached": 0}, update_modified=False
	)


def stop_clock(contact):
	if frappe.db.get_value(CONTACT, contact, "sla_due_at"):
		frappe.db.set_value(CONTACT, contact, {"sla_due_at": None, "sla_breached": 0}, update_modified=False)


def check_overdue():
	from onechat.inbox.conversations import publish

	for row in frappe.get_all(
		CONTACT,
		filters={"sla_due_at": ["<=", now_datetime()], "sla_breached": 0, "conversation_status": "Open"},
		fields=["name", "contact_name", "mobile_no", "assigned_to"],
		limit_page_length=200,
	):
		frappe.db.set_value(CONTACT, row.name, "sla_breached", 1, update_modified=False)
		title = row.contact_name or row.mobile_no or row.name
		for user in [row.assigned_to] if row.assigned_to else admins():
			frappe.get_doc(
				{
					"doctype": "Notification Log",
					"subject": _("Reply overdue: {0} is still waiting for a first reply").format(title),
					"for_user": user,
					"type": "Alert",
					"document_type": CONTACT,
					"document_name": row.name,
				}
			).insert(ignore_permissions=True)
			frappe.publish_realtime(
				"onechat_reminder",
				{
					"contact": row.name,
					"contact_name": title,
					"kind": "sla",
					"text": _("The reply time has passed."),
				},
				user=user,
				after_commit=True,
			)
		publish(row.name)


def admins():
	from onechat.insights.costs import admins as admin_users

	return admin_users()


def run():
	if cint(settings().get("sla_enabled")):
		check_overdue()


def window_open(contact):
	last = frappe.db.get_value(
		MESSAGE, {"whatsapp_contact": contact, "type": "Incoming"}, "creation", order_by="creation desc"
	)
	return bool(last) and get_datetime(last) > add_to_date(now_datetime(), hours=-REPLY_WINDOW_HOURS)


def latest_conversation(contact):
	return frappe.db.get_value(
		CONVERSATION, {"contact": contact}, ["name", "csat_asked_at"], as_dict=True, order_by="opened_at desc"
	)


def send_survey(contact):
	config = settings()
	if not cint(config.get("csat_enabled")) or not window_open(contact):
		return
	conversation = latest_conversation(contact)
	if not conversation or conversation.csat_asked_at:
		return
	phone = frappe.db.get_value(CONTACT, contact, "mobile_no")
	if not phone:
		return
	buttons = [
		{"id": f"{SURVEY_PREFIX}{score}", "title": f"{RATING_ICONS[score]} {_(label)}"}
		for score, label in RATINGS
	]
	message = frappe.get_doc(
		{
			"doctype": MESSAGE,
			"type": "Outgoing",
			"message_type": "Manual",
			"source": "Auto reply",
			"to": phone,
			"content_type": "interactive",
			"message": config.get("csat_message") or _("How did we do today? Tap a rating below."),
			"buttons": json.dumps(buttons),
			"reference_doctype": CONTACT,
			"reference_name": contact,
		}
	)
	message.flags.onechat_survey = True
	message.insert(ignore_permissions=True)
	frappe.db.set_value(
		CONVERSATION, conversation.name, "csat_asked_at", now_datetime(), update_modified=False
	)


def survey_reply(doc):
	if doc.type != "Incoming" or doc.content_type != "button":
		return None
	try:
		reply = json.loads(doc.buttons or "{}").get("reply_id") or ""
	except (ValueError, AttributeError):
		return None
	if not reply.startswith(SURVEY_PREFIX):
		return None
	score = cint(reply[len(SURVEY_PREFIX) :])
	return score if score in RATING_ICONS else None


def record_survey(doc, contact):
	score = survey_reply(doc)
	if not score:
		return False
	conversation = frappe.db.get_value(
		CONVERSATION,
		{
			"contact": contact,
			"csat_asked_at": [">=", add_to_date(now_datetime(), hours=-SURVEY_WINDOW_HOURS)],
		},
		["name", "csat_score"],
		as_dict=True,
		order_by="csat_asked_at desc",
	)
	if not conversation:
		return False
	doc.flags.onechat_survey = True
	if not conversation.csat_score:
		frappe.db.set_value(
			CONVERSATION,
			conversation.name,
			{"csat_score": score, "csat_at": now_datetime()},
			update_modified=False,
		)
		phone = frappe.db.get_value(CONTACT, contact, "mobile_no")
		if phone:
			thanks = frappe.get_doc(
				{
					"doctype": MESSAGE,
					"type": "Outgoing",
					"message_type": "Manual",
					"source": "Auto reply",
					"to": phone,
					"content_type": "text",
					"message": _("Thank you for your feedback!"),
					"reference_doctype": CONTACT,
					"reference_name": contact,
				}
			)
			thanks.flags.onechat_survey = True
			thanks.insert(ignore_permissions=True)
	return True
