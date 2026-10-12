import frappe

LINK = "OneChat Chat Link"


def execute():
	for name in frappe.get_all(LINK, pluck="name"):
		doc = frappe.get_doc(LINK, name)
		doc.flags.ignore_permissions = True
		doc.save()
