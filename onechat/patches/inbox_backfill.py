import frappe

from onechat.inbox.conversations import CONTACT, MESSAGE, digits, ensure_contact, preview


def execute():
	for contact in frappe.get_all(CONTACT, fields=["name", "mobile_no"]):
		frappe.db.set_value(
			CONTACT, contact.name, "wa_number", digits(contact.mobile_no), update_modified=False
		)

	for message in frappe.get_all(
		MESSAGE,
		filters={"whatsapp_contact": ["is", "not set"]},
		fields=["name", "type", "from", "to", "profile_name", "reference_doctype", "reference_name"],
		order_by="creation asc",
	):
		if message.reference_doctype == CONTACT and message.reference_name:
			contact = message.reference_name
		else:
			contact = ensure_contact(message)
		if not contact:
			continue

		links = {"whatsapp_contact": contact}
		if not message.reference_doctype:
			links.update({"reference_doctype": CONTACT, "reference_name": contact})
		frappe.db.set_value(MESSAGE, message.name, links, update_modified=False)

	for contact in frappe.get_all(CONTACT, pluck="name"):
		last = frappe.get_all(
			MESSAGE,
			filters={"whatsapp_contact": contact, "content_type": ["!=", "reaction"]},
			fields=["type", "message", "message_type", "template", "content_type", "creation"],
			order_by="creation desc",
			limit=1,
		)
		if not last:
			continue

		frappe.db.set_value(
			CONTACT,
			contact,
			{
				"last_message": preview(last[0]),
				"last_message_at": last[0].creation,
				"last_message_type": last[0].type or "Outgoing",
			},
			update_modified=False,
		)
