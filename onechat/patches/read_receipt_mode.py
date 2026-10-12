import frappe

ACCOUNT = "OneChat Account"


def execute():
	meta = frappe.get_meta(ACCOUNT)
	if not meta.has_field("read_receipts") or not meta.has_field("allow_auto_read_receipt"):
		return
	account = frappe.qb.DocType(ACCOUNT)
	frappe.qb.update(account).set(account.read_receipts, "Never").where(
		account.allow_auto_read_receipt == 0
	).run()
	frappe.qb.update(account).set(account.read_receipts, "When an agent opens the chat").where(
		(account.allow_auto_read_receipt == 1)
		& (account.read_receipts.isnull() | (account.read_receipts == ""))
	).run()
