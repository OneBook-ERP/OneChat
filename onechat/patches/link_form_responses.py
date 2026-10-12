import frappe

from onechat.campaigns.forms import resolve_form

MESSAGE = "OneChat Message"


def execute():
	rows = frappe.get_all(
		MESSAGE,
		filters={"type": "Incoming", "content_type": "flow", "flow": ["is", "not set"]},
		fields=["name", "flow_response", "reply_to_message_id"],
		limit_page_length=0,
	)

	for row in rows:
		try:
			response = frappe.parse_json(row.flow_response or "{}")
		except ValueError:
			continue
		if not isinstance(response, dict):
			continue

		flow = resolve_form(response, row.reply_to_message_id)
		if flow:
			frappe.db.set_value(MESSAGE, row.name, "flow", flow, update_modified=False)
