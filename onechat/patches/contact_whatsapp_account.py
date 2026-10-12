import frappe
from frappe.query_builder.functions import Max

CONTACT = "OneChat Contact"
MESSAGE = "OneChat Message"
CHUNK = 500


def execute():
	accounts = frappe.get_all("OneChat Account", pluck="name")
	if not accounts:
		return

	contact = frappe.qb.DocType(CONTACT)
	if len(accounts) == 1:
		frappe.qb.update(contact).set(contact.whatsapp_account, accounts[0]).where(
			contact.whatsapp_account.isnull()
		).run()
		return

	message = frappe.qb.DocType(MESSAGE)
	rows = (
		frappe.qb.from_(message)
		.select(message.whatsapp_contact, message.whatsapp_account, Max(message.creation).as_("latest"))
		.where(message.whatsapp_contact.isnotnull() & message.whatsapp_account.isnotnull())
		.groupby(message.whatsapp_contact, message.whatsapp_account)
		.run(as_dict=True)
	)
	latest = {}
	for row in rows:
		if row.whatsapp_contact not in latest or row.latest > latest[row.whatsapp_contact][1]:
			latest[row.whatsapp_contact] = (row.whatsapp_account, row.latest)

	by_account = {}
	for name, (account, _) in latest.items():
		by_account.setdefault(account, []).append(name)

	for account, names in by_account.items():
		for start in range(0, len(names), CHUNK):
			(
				frappe.qb.update(contact)
				.set(contact.whatsapp_account, account)
				.where(contact.name.isin(names[start : start + CHUNK]) & contact.whatsapp_account.isnull())
				.run()
			)
