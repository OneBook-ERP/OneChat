import frappe


def execute():
	frappe.db.set_value(
		"OneChat Account", {"status": ["!=", "Active"]}, "status", "Active", update_modified=False
	)
