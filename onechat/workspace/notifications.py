import json
import re

import frappe
from frappe import _
from frappe.utils import cint, strip_html

from onechat.api_types import JSON
from onechat.workspace.session import is_admin, require_app_user

KEY = "onechat_notifications"
TONES = ("chime", "pop", "ding", "soft")
TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
EVENTS = ("new_chat", "my_messages", "mentions", "assigned", "reminders", "payments", "all_messages")
DEFAULTS = {
	"desktop": 1,
	"events": {
		"new_chat": 1,
		"my_messages": 1,
		"mentions": 1,
		"assigned": 1,
		"reminders": 1,
		"payments": 1,
		"all_messages": 0,
	},
	"sound": 1,
	"tone": "chime",
	"volume": 70,
	"quiet": 0,
	"quiet_from": "21:00",
	"quiet_to": "08:00",
	"tab_badge": 1,
	"feed_scope": "onechat",
}
SCOPES = ("onechat", "all")
MODULE_DOCTYPES = "onechat:notification-doctypes"


def stored(user=None):
	value = frappe.defaults.get_user_default(KEY, user=user)
	try:
		return json.loads(value) if value else {}
	except ValueError:
		return {}


def merged(values):
	out = {**DEFAULTS, **{key: values[key] for key in DEFAULTS if key in values}}
	out["events"] = {**DEFAULTS["events"], **(values.get("events") or {})}
	return out


def clean(values):
	out = merged(values)
	for key in ("desktop", "sound", "quiet", "tab_badge"):
		out[key] = 1 if out[key] else 0
	out["events"] = {key: 1 if out["events"].get(key) else 0 for key in EVENTS}
	if not is_admin():
		out["events"]["all_messages"] = 0
	if out["feed_scope"] not in SCOPES:
		out["feed_scope"] = DEFAULTS["feed_scope"]
	if out["tone"] not in TONES:
		out["tone"] = DEFAULTS["tone"]
	try:
		out["volume"] = max(0, min(100, int(out["volume"])))
	except (TypeError, ValueError):
		out["volume"] = DEFAULTS["volume"]
	for key in ("quiet_from", "quiet_to"):
		if not TIME.match(str(out[key] or "")):
			out[key] = DEFAULTS[key]
	return out


@frappe.whitelist()
def get():
	require_app_user()
	return clean(stored())


@frappe.whitelist()
def save(values: JSON):
	require_app_user()
	values = frappe.parse_json(values) or {}
	for key in ("quiet_from", "quiet_to"):
		if key in values and not TIME.match(str(values[key] or "")):
			frappe.throw(_("Quiet hours need a time like 21:00."))
	values = clean(values)
	frappe.defaults.set_user_default(KEY, json.dumps(values))
	return values


LOG = "Notification Log"
FEED_LIMIT = 50


def notify(user, subject, doctype=None, name=None, kind="Alert", from_user=None):
	sender = from_user or frappe.session.user
	if not user or user == "Guest" or (kind == "Assignment" and user == sender):
		return
	frappe.get_doc(
		{
			"doctype": LOG,
			"subject": subject,
			"for_user": user,
			"type": kind,
			"document_type": doctype,
			"document_name": name,
			"from_user": sender if sender != "Guest" else "Administrator",
		}
	).insert(ignore_permissions=True)


PAYMENT_ALERT = "onechat:payment-alert:{0}"


def payment_alert(key, contact, amount, document, senders=()):
	cache_key = PAYMENT_ALERT.format(key)
	if frappe.cache().get_value(cache_key, expires=True):
		return []
	frappe.cache().set_value(cache_key, 1, expires_in_sec=86400)
	row = frappe.db.get_value(
		"OneChat Contact", contact, ["contact_name", "mobile_no", "assigned_to"], as_dict=True
	)
	if not row:
		return []
	title = row.contact_name or row.mobile_no or contact
	text = _("{0} paid by {1} for {2}").format(amount, title, document)
	users = [
		user
		for user in dict.fromkeys([row.assigned_to] if row.assigned_to else senders)
		if user and user != "Guest"
	]
	told = []
	for user in users:
		if not merged(stored(user))["events"].get("payments"):
			continue
		notify(user, text, "OneChat Contact", contact, "Alert", "Administrator")
		frappe.publish_realtime(
			"onechat_payment",
			{"contact": contact, "contact_name": title, "amount": amount, "document": document, "text": text},
			user=user,
			after_commit=True,
		)
		told.append(user)
	return told


def onechat_doctypes():
	cached = frappe.cache().get_value(MODULE_DOCTYPES)
	if cached is None:
		cached = frappe.get_all("DocType", filters={"module": "OneChat"}, pluck="name")
		frappe.cache().set_value(MODULE_DOCTYPES, cached, expires_in_sec=86400)
	return cached


def scoped(filters):
	if clean(stored())["feed_scope"] == "onechat":
		filters["document_type"] = ["in", onechat_doctypes() or [""]]
	return filters


@frappe.whitelist()
def feed(unread: bool | int | str = 0, start: int | str = 0, limit: int | str = FEED_LIMIT):
	require_app_user()
	filters = scoped({"for_user": frappe.session.user})
	if cint(unread):
		filters["read"] = 0
	rows = frappe.get_all(
		LOG,
		filters=filters,
		fields=["name", "subject", "type", "document_type", "document_name", "from_user", "read", "creation"],
		order_by="creation desc",
		limit_start=cint(start),
		limit_page_length=min(cint(limit) or FEED_LIMIT, 100),
	)
	for row in rows:
		row.subject = strip_html(row.subject or "").strip()
		row.creation = str(row.creation)
	return {"items": rows, "unread": unread_count()}


def unread_count():
	return frappe.db.count(LOG, scoped({"for_user": frappe.session.user, "read": 0}))


@frappe.whitelist()
def count():
	require_app_user()
	return unread_count()


@frappe.whitelist(methods=["POST"])
def mark_read(names: JSON = None):
	require_app_user()
	names = [name for name in frappe.parse_json(names) or [] if name]
	filters = scoped({"for_user": frappe.session.user, "read": 0})
	if names:
		filters["name"] = ["in", names]
	for name in frappe.get_all(LOG, filters=filters, pluck="name"):
		frappe.db.set_value(LOG, name, "read", 1, update_modified=False)
	return unread_count()
