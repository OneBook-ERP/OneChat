import frappe


def execute():
	if frappe.db.exists("DocType", "WhatsApp Profiles"):
		frappe.delete_doc("DocType", "WhatsApp Profiles", force=True, ignore_missing=True)
