import frappe

RENAMES = {
	"WhatsApp Account": "OneChat Account",
	"WhatsApp Contact": "OneChat Contact",
	"WhatsApp Message": "OneChat Message",
}


def move_passwords():
	auth = frappe.qb.Table("__Auth")
	for old, new in RENAMES.items():
		frappe.qb.update(auth).set(auth.doctype, new).where(auth.doctype == old).run()


def execute():
	for old, new in RENAMES.items():
		if frappe.db.exists("DocType", old) and not frappe.db.exists("DocType", new):
			frappe.rename_doc("DocType", old, new, force=True)
	move_passwords()
	frappe.clear_cache()
