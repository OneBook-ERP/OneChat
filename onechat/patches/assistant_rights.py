import frappe

ROLE = "OneChat Assistant Role"


def execute():
	if not frappe.get_meta(ROLE).has_field("can_create"):
		return
	row = frappe.qb.DocType(ROLE)
	frappe.qb.update(row).set(row.can_read, 1).set(row.can_write, 1).set(row.can_create, 1).where(
		row.access == "Read and write"
	).run()
	frappe.qb.update(row).set(row.can_read, 1).set(row.can_write, 0).set(row.can_create, 0).where(
		row.access != "Read and write"
	).run()
