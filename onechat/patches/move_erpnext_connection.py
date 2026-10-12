import frappe
from frappe.utils.password import get_decrypted_password

SETTINGS = "WhatsApp Settings"
CONNECTION = "OneChat Connection"
FIELDS = ("mode", "url", "api_key", "connected", "status", "checked_at", "webhooks")


def execute():
	if frappe.db.exists(CONNECTION, "erpnext"):
		return

	singles = frappe.qb.DocType("Singles")
	rows = (
		frappe.qb.from_(singles)
		.select(singles.field, singles.value)
		.where((singles.doctype == SETTINGS) & singles.field.like("erpnext\\_%"))
		.run()
	)
	old = {field.replace("erpnext_", "", 1): value for field, value in rows}
	if not old.get("mode"):
		return

	doc = frappe.get_doc(
		{
			"doctype": CONNECTION,
			"integration": "erpnext",
			**{key: old.get(key) for key in FIELDS if old.get(key)},
		}
	)
	for field in ("api_secret", "webhook_secret"):
		secret = get_decrypted_password(SETTINGS, SETTINGS, f"erpnext_{field}", raise_exception=False)
		if secret:
			doc.set(field, secret)
	doc.insert(ignore_permissions=True)
