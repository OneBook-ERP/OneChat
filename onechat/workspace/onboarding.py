import json

import frappe
from frappe.utils import cint

from onechat import integrations
from onechat.api_types import JSON
from onechat.workspace.session import require_admin

DISMISSED = "onechat_onboarding_dismissed"
MARKED = "onechat_onboarding_marked"
ACCOUNT = "OneChat Account"
SETTINGS = "OneChat Settings"


def exists(doctype, filters=None):
	return bool(frappe.get_all(doctype, filters=filters or {}, limit=1, pluck="name"))


def marked():
	try:
		value = json.loads(frappe.db.get_default(MARKED) or "[]")
	except ValueError:
		value = []
	return [key for key in value if isinstance(key, str)]


def assistant_ready(settings):
	from onechat.assistant.api import key_of

	return bool(cint(settings.get("assistant_enabled")) and key_of(settings))


@frappe.whitelist()
def status():
	require_admin()
	settings = frappe.get_cached_doc(SETTINGS)
	steps = {
		"connect": exists(ACCOUNT, {"connection_status": "Connected"})
		or exists(ACCOUNT, {"webhook_last_event_at": ["is", "set"]}),
		"webhook": exists(ACCOUNT, {"webhook_verified_at": ["is", "set"]})
		or exists(ACCOUNT, {"webhook_last_event_at": ["is", "set"]}),
		"templates": exists("WhatsApp Templates", {"status": ["in", ["APPROVED", "Approved"]]}),
		"instagram": exists(ACCOUNT, {"channel": "Instagram", "connection_status": "Connected"}),
		"team": frappe.db.count("OneChat User", {"enabled": 1}) > 1,
		"rules": bool(settings.get("auto_assign") or settings.get("business_hours_enabled")),
		"teams": exists("OneChat Team"),
		"quick_replies": exists("OneChat Quick Reply"),
		"labels": exists("OneChat Label"),
		"chatbot": exists("OneChat Flow", {"is_active": 1}),
		"auto_replies": exists("OneChat Auto Reply", {"enabled": 1}),
		"chat_link": exists("OneChat Chat Link"),
		"first_message": exists("OneChat Message", {"type": "Outgoing"}),
		"assistant": assistant_ready(settings),
	}
	if any(spec["installed"] for spec in integrations.registered()):
		steps["integrations"] = exists("OneChat Contact", {"reference_docname": ["is", "set"]})

	manual = [key for key in marked() if key in steps]
	detected = [key for key, done in steps.items() if done]
	for key in manual:
		steps[key] = True

	return {
		"steps": steps,
		"marked": [key for key in manual if key not in detected],
		"dismissed": bool(cint(frappe.defaults.get_user_default(DISMISSED))),
	}


@frappe.whitelist(methods=["POST"])
def mark(step: str, done: int | str = 1):
	require_admin()
	keys = set(marked())
	if cint(done):
		keys.add(step)
	else:
		keys.discard(step)
	frappe.db.set_default(MARKED, json.dumps(sorted(keys)))
	return status()


@frappe.whitelist(methods=["POST"])
def dismiss(value: JSON = 1):
	require_admin()
	frappe.defaults.set_user_default(DISMISSED, 1 if cint(value) else 0)
	return status()
