import frappe


def execute():
	link = frappe.qb.DocType("OneChat Contact Link")
	frappe.qb.update(link).set(link.main, 1).where(link.parenttype == "OneChat Contact").run()
