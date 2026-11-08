import frappe
from frappe import _

from onechat.api_types import JSON
from onechat.automation import run_as
from onechat.integrations import connection
from onechat.workspace.session import require_admin

BASE_CHECKS = (
	("OneChat Contact", "write"),
	("OneChat Message", "create"),
	("OneChat Note", "create"),
)
ERPNEXT_CHECKS = (
	("Customer", "create"),
	("Contact", "create"),
	("Address", "create"),
	("Item", "read"),
	("Quotation", "create"),
	("Quotation", "submit"),
	("Sales Order", "create"),
	("Sales Order", "submit"),
	("Sales Invoice", "read"),
)
PAYMENT_CHECKS = (
	("Payment Request", "create"),
	("Payment Request", "submit"),
	("Payment Entry", "create"),
	("Payment Entry", "submit"),
)
CRM_CHECKS = (
	("CRM Lead", "create"),
	("CRM Lead", "write"),
	("CRM Deal", "read"),
)


def user_options():
	rows = frappe.get_all(
		"User",
		filters={"enabled": 1, "user_type": "System User", "name": ["!=", "Guest"]},
		fields=["name", "full_name"],
		order_by="full_name asc",
		limit_page_length=0,
	)
	return [{"value": row.name, "label": f"{row.full_name or row.name} ({row.name})"} for row in rows]


def remote_rows():
	rows = []
	for key in connection.APPS:
		site = connection.site(key)
		if not site.is_remote():
			continue
		api_key, secret = site.automation_credentials()
		rows.append(
			{
				"key": key,
				"label": site.label,
				"url": site.base_url(),
				"api_key": api_key or "",
				"has_secret": bool(secret),
			}
		)
	return rows


@frappe.whitelist()
def get_settings():
	require_admin()
	return {
		"user": frappe.db.get_single_value(run_as.SETTINGS, run_as.FIELD) or "",
		"users": user_options(),
		"sites": remote_rows(),
	}


def save_site(row):
	site = connection.site(row.get("key"))
	if not site.is_remote():
		return
	api_key = (row.get("api_key") or "").strip()
	secret = (row.get("api_secret") or "").strip()
	if not api_key:
		site.update({"automation_api_key": None, "automation_api_secret": None})
		return
	if not secret and not site.automation_credentials()[1]:
		frappe.throw(_("Add the automation API secret for {0}.").format(site.label))
	values = {"automation_api_key": api_key}
	if secret:
		values["automation_api_secret"] = secret
	site.update(values)


@frappe.whitelist(methods=["POST"])
def save_settings(user: str | None = None, sites: JSON = None):
	require_admin()
	settings = frappe.get_doc(run_as.SETTINGS)
	settings.set(run_as.FIELD, (user or "").strip() or None)
	settings.flags.ignore_permissions = True
	settings.save()
	for row in frappe.parse_json(sites) if sites else []:
		save_site(row)
	return get_settings()


def local_checks():
	checks = list(BASE_CHECKS)
	erpnext = connection.site("erpnext")
	if erpnext.ready() and not erpnext.is_remote():
		checks += ERPNEXT_CHECKS
		from onechat.integrations.extras import payments_active

		if payments_active():
			checks += PAYMENT_CHECKS
	crm = connection.site("crm")
	if crm.ready() and not crm.is_remote():
		checks += CRM_CHECKS
	return [(doctype, action) for doctype, action in checks if frappe.db.exists("DocType", doctype)]


def local_access(user):
	return [
		{
			"doctype": doctype,
			"action": action,
			"ok": bool(frappe.has_permission(doctype, action, user=user)),
		}
		for doctype, action in local_checks()
	]


def remote_access(site):
	if not site.automation_credentials()[0]:
		return {"label": site.label, "ok": True, "user": None}
	try:
		with run_as.switched(None):
			user = site.client().call("frappe.auth.get_logged_user")
		return {"label": site.label, "ok": True, "user": user}
	except frappe.ValidationError as error:
		frappe.clear_last_message()
		return {"label": site.label, "ok": False, "error": str(error)}


@frappe.whitelist()
def check_access():
	require_admin()
	user = run_as.automation_user()
	return {
		"user": user,
		"local": local_access(user) if user else [],
		"sites": [remote_access(connection.site(row["key"])) for row in remote_rows()],
	}
