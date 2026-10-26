import frappe

from onechat.inbox import contact_accounts

CONTACT = "OneChat Contact"


def execute():
	frappe.reload_doc("onechat", "doctype", "onechat_contact_account")
	frappe.reload_doc("onechat", "doctype", "onechat_contact")
	names = frappe.get_all(CONTACT, filters={"last_message_at": ["is", "set"]}, pluck="name")
	for index, name in enumerate(names, start=1):
		contact_accounts.backfill(name)
		if index % contact_accounts.BATCH == 0:
			frappe.db.commit()  # nosemgrep: frappe-manual-commit - long backfill, keep progress across batches
