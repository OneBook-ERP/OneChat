import frappe


def execute():
	contact = frappe.qb.DocType("OneChat Contact")
	(
		frappe.qb.update(contact)
		.set(contact.conversation_status, "Open")
		.where(contact.conversation_status.isnull() | (contact.conversation_status == ""))
	).run()
