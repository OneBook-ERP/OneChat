import frappe
from frappe.utils import add_days, now_datetime

STALE_DAYS = 30


def execute():
	contact = frappe.qb.DocType("OneChat Contact")
	cutoff = add_days(now_datetime(), -STALE_DAYS)
	(
		frappe.qb.update(contact)
		.set(contact.conversation_status, "Resolved")
		.set(contact.resolved_by, "Administrator")
		.set(contact.resolved_at, now_datetime())
		.where(
			(contact.conversation_status == "Open")
			& (
				(contact.last_message_at < cutoff)
				| (contact.last_message_at.isnull() & (contact.modified < cutoff))
			)
		)
	).run()
