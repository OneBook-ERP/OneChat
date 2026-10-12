import frappe

LIVE = "Fetch live from Meta"


def execute():
	singles = frappe.qb.DocType("Singles")
	value = (
		frappe.qb.from_(singles)
		.select(singles.value)
		.where((singles.doctype == "WhatsApp Settings") & (singles.field == "spend_storage"))
		.run(pluck=True)
	)
	if not value or value[0] != LIVE or not frappe.get_meta("OneChat Account").has_field("spend_storage"):
		return
	account = frappe.qb.DocType("OneChat Account")
	frappe.qb.update(account).set(account.spend_storage, LIVE).run()
