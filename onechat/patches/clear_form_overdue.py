import frappe

CONTACT = "OneChat Contact"
MESSAGE = "OneChat Message"


def execute():
	for name in frappe.get_all(CONTACT, filters={"sla_due_at": ["is", "set"]}, pluck="name"):
		last = frappe.get_all(
			MESSAGE,
			filters={"whatsapp_contact": name, "content_type": ["!=", "reaction"]},
			fields=["type", "content_type", "source"],
			order_by="creation desc",
			limit_page_length=1,
		)
		if not last:
			continue
		row = last[0]
		answered = row.type == "Outgoing" and row.source in ("Agent", "Bot")
		form_only = row.type == "Incoming" and row.content_type == "flow"
		if answered or form_only:
			frappe.db.set_value(CONTACT, name, {"sla_due_at": None, "sla_breached": 0}, update_modified=False)
	for name in frappe.get_all(
		CONTACT, filters={"sla_due_at": ["is", "set"], "conversation_status": "Pending"}, pluck="name"
	):
		frappe.db.set_value(CONTACT, name, {"sla_due_at": None, "sla_breached": 0}, update_modified=False)
