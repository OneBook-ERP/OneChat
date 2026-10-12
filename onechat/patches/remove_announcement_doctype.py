import frappe

DOCTYPE = "OneChat Announcement"


def execute():
	if frappe.db.exists("DocType", DOCTYPE):
		frappe.delete_doc("DocType", DOCTYPE, force=True, ignore_missing=True)
	frappe.db.sql_ddl(f"drop table if exists `tab{DOCTYPE}`")
