import frappe

OLD = "OneChat User"
NEW = "OneChat Agent"


def execute():
	if not frappe.db.exists("Role", OLD):
		return

	frappe.rename_doc(
		"Role", OLD, NEW, force=True, merge=bool(frappe.db.exists("Role", NEW)), show_alert=False
	)
	frappe.db.set_value("Role", NEW, "role_name", NEW)
	frappe.clear_cache()
