import json

import frappe
from frappe import _

from onechat import integrations
from onechat.api_types import JSON
from onechat.inbox.conversations import CONTACT, guard, publish
from onechat.inbox.visibility import check as check_visible
from onechat.integrations import connection, links
from onechat.workspace.session import is_admin


def admin_only():
	if not is_admin():
		frappe.throw(_("Only OneChat admins can change integrations."), frappe.PermissionError)


def remote_site(spec):
	key = spec.get("setup")
	if key in connection.APPS:
		row = connection.site(key)
		if row.is_remote():
			return row
	return None


def host(url):
	from urllib.parse import urlparse

	return urlparse(url or "").netloc or url or ""


def app_site(key):
	row = connection.site(key)
	if row.is_remote():
		values = row.row()
		return {
			"label": host(row.base_url()),
			"url": row.base_url(),
			"remote": True,
			"auth": _("Sign in (OAuth)") if row.uses_oauth() else _("API key"),
			"user": values.get("oauth_user") or "",
			"ready": row.ready(),
			"last_event_at": values.get("last_event_at"),
			"last_event": values.get("last_event") or "",
		}
	return {
		"label": frappe.local.site,
		"url": "",
		"remote": False,
		"auth": "",
		"user": "",
		"ready": row.installed_here(),
	}


def where(spec):
	if spec.get("where"):
		try:
			return integrations.run(spec["where"]) or []
		except Exception:
			frappe.log_error(title=f"OneChat integration location: {spec['name']}")
			return []
	if spec.get("setup") in connection.APPS:
		return [app_site(spec["setup"])]
	return (
		[
			{
				"label": frappe.local.site,
				"url": "",
				"remote": False,
				"auth": "",
				"user": "",
				"ready": spec["installed"],
			}
		]
		if spec["installed"]
		else []
	)


def public(spec, off):
	return {
		"name": spec["name"],
		"label": spec["label"],
		"icon": spec.get("icon"),
		"logo": spec.get("logo"),
		"category": spec.get("category") or _("Apps"),
		"description": spec.get("description"),
		"features": spec.get("features") or [],
		"docs_url": spec.get("docs_url"),
		"app": spec.get("app"),
		"installed": spec["installed"],
		"enabled": spec["installed"]
		and (bool(integrations.run(spec["active"])) if spec.get("active") else spec["name"] not in off),
		"link_doctypes": spec.get("link_doctypes", []),
		"purchases": bool(spec.get("metrics")),
		"records": bool(spec.get("timeline")),
		"setup": spec.get("setup"),
		"desk_url": remote_site(spec).base_url() if remote_site(spec) else "",
		"mode": connection.site(spec["setup"]).mode() if spec.get("setup") in connection.APPS else None,
		"where": where(spec),
		"sites_help": spec.get("sites_help") or "",
	}


@frappe.whitelist()
def available():
	guard()

	off = integrations.disabled()
	return {
		"integrations": [public(spec, off) for spec in integrations.registered()],
		"auto_link": not integrations.setting("disable_auto_link"),
		"create_customer_on_win": bool(integrations.setting("create_customer_on_win")),
	}


@frappe.whitelist()
def set_enabled(name: str, enabled: JSON):
	admin_only()

	off = integrations.disabled()
	if frappe.parse_json(enabled):
		off.discard(name)
	else:
		off.add(name)
	integrations.save_setting("disabled_integrations", json.dumps(sorted(off)))

	return available()


@frappe.whitelist()
def set_auto_link(enabled: JSON):
	admin_only()

	integrations.save_setting("disable_auto_link", 0 if frappe.parse_json(enabled) else 1)

	return available()


@frappe.whitelist()
def set_create_customer_on_win(enabled: JSON):
	admin_only()

	integrations.save_setting("create_customer_on_win", 1 if frappe.parse_json(enabled) else 0)

	return available()


@frappe.whitelist()
def contact(contact: str):
	guard()
	check_visible(contact)

	doc = frappe.get_doc(CONTACT, contact)
	return {
		"cards": integrations.cards(doc),
		"actions": integrations.actions(doc),
		"links": links.public(doc),
	}


def attach(contact, doctype, name):
	links.add(contact, doctype, name)
	integrations.linked(contact, doctype, name)


@frappe.whitelist()
def link(contact: str, doctype: str | None = None, name: str | None = None, integration: str | None = None):
	guard()
	check_visible(contact)

	if doctype and doctype not in integrations.link_doctypes():
		frappe.throw(_("{0} is not a linkable record type.").format(doctype))
	if doctype and name and not connection.source_for(doctype).exists(doctype, name):
		frappe.throw(_("{0} {1} does not exist.").format(_(doctype), name))

	if doctype and name:
		attach(contact, doctype, name)
	else:
		keys = (
			[integration or links.owner(doctype)]
			if integration or doctype
			else [row.integration for row in links.of(contact)]
		)
		for key in keys:
			links.remove(contact, key)
	publish(contact)

	return contact_state(contact)


@frappe.whitelist()
def unlink_record(contact: str, doctype: str, name: str):
	guard()
	check_visible(contact)

	links.unlink(contact, doctype, name)
	publish(contact)

	return contact_state(contact)


@frappe.whitelist()
def make_main(contact: str, doctype: str, name: str):
	guard()
	check_visible(contact)

	links.make_main(contact, doctype, name)
	integrations.linked(contact, doctype, name)
	publish(contact)

	return contact_state(contact)


@frappe.whitelist()
def make_primary(contact: str, integration: str):
	guard()
	check_visible(contact)

	links.make_primary(contact, integration)
	publish(contact)

	return contact_state(contact)


@frappe.whitelist()
def auto_link(contact: str):
	guard()
	check_visible(contact)

	found = integrations.auto_link(frappe.get_doc(CONTACT, contact))
	for doctype, name in found:
		attach(contact, doctype, name)
	if found:
		publish(contact)

	return contact_state(contact, found=[name for doctype, name in found])


@frappe.whitelist()
def run_action(contact: str, integration: str, action: str, payload: JSON = None):
	guard()
	check_visible(contact)

	doc = frappe.get_doc(CONTACT, contact)
	result = integrations.perform(doc, integration, action, frappe.parse_json(payload) if payload else None)
	if isinstance(result, list | tuple) and len(result) == 2:
		attach(contact, result[0], result[1])
		publish(contact)

	return contact_state(contact, result)


@frappe.whitelist()
def run_row_action(contact: str, integration: str, key: str, doctype: str, name: str):
	guard()
	check_visible(contact)

	doc = frappe.get_doc(CONTACT, contact)
	result = integrations.perform_row(doc, integration, key, doctype, name)

	return contact_state(contact, result)


def contact_state(contact, result=None, found=None):
	doc = frappe.get_doc(CONTACT, contact)
	return {
		"reference_doctype": doc.reference_doctype,
		"reference_docname": doc.reference_docname,
		"links": links.public(doc),
		"found": found or [],
		"cards": integrations.cards(doc),
		"actions": integrations.actions(doc),
		"message": result if isinstance(result, str) else None,
	}
