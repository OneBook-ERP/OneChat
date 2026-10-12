import frappe
from frappe.query_builder.functions import Count

BROADCAST = "Bulk WhatsApp Message"
MESSAGE = "OneChat Message"


def execute():
	if not frappe.get_meta(BROADCAST).has_field("whatsapp_account"):
		return

	message = frappe.qb.DocType(MESSAGE)
	rows = (
		frappe.qb.from_(message)
		.select(message.bulk_message_reference, message.whatsapp_account, Count("*").as_("count"))
		.where(message.bulk_message_reference.isnotnull() & message.whatsapp_account.isnotnull())
		.groupby(message.bulk_message_reference, message.whatsapp_account)
		.run(as_dict=True)
	)
	best = {}
	for row in rows:
		if row.count > best.get(row.bulk_message_reference, (None, 0))[1]:
			best[row.bulk_message_reference] = (row.whatsapp_account, row.count)

	for name, (account, _) in best.items():
		frappe.db.set_value(BROADCAST, name, "whatsapp_account", account, update_modified=False)
