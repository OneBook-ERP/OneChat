import frappe
from frappe import _
from frappe.query_builder import Order


def execute(filters=None):
	if not filters:
		filters = {}

	columns = get_columns()
	data = get_data(filters)

	return columns, data


def get_columns():
	return [
		{
			"fieldname": "name",
			"label": _("ID"),
			"fieldtype": "Link",
			"options": "Bulk WhatsApp Message",
			"width": 120,
		},
		{"fieldname": "title", "label": _("Title"), "fieldtype": "Data", "width": 180},
		{"fieldname": "creation", "label": _("Created On"), "fieldtype": "Datetime", "width": 150},
		{"fieldname": "recipient_count", "label": _("Total Recipients"), "fieldtype": "Int", "width": 120},
		{"fieldname": "sent_count", "label": _("Messages Sent"), "fieldtype": "Int", "width": 120},
		{"fieldname": "delivered_count", "label": _("Delivered"), "fieldtype": "Int", "width": 100},
		{"fieldname": "read_count", "label": _("Read"), "fieldtype": "Int", "width": 100},
		{"fieldname": "failed_count", "label": _("Failed"), "fieldtype": "Int", "width": 100},
		{"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 120},
	]


def get_data(filters):
	bulk = frappe.qb.DocType("Bulk WhatsApp Message")
	query = (
		frappe.qb.from_(bulk)
		.select(bulk.name, bulk.title, bulk.creation, bulk.recipient_count, bulk.sent_count, bulk.status)
		.where(bulk.docstatus == 1)
		.orderby(bulk.creation, order=Order.desc)
	)

	if filters.get("from_date") and filters.get("to_date"):
		query = query.where(bulk.creation.between(filters.get("from_date"), filters.get("to_date")))

	if filters.get("status"):
		query = query.where(bulk.status == filters.get("status"))

	if filters.get("from_number"):
		query = query.where(bulk.from_number == filters.get("from_number"))

	from onechat.workspace import numbers

	shown = numbers.condition(bulk)
	if shown is not None:
		query = query.where(shown)

	data = query.run(as_dict=True)

	for row in data:
		row["delivered_count"] = frappe.db.count(
			"OneChat Message", {"bulk_message_reference": row.name, "status": "delivered"}
		)

		row["read_count"] = frappe.db.count(
			"OneChat Message", {"bulk_message_reference": row.name, "status": "read"}
		)

		row["sent_count"] = frappe.db.count(
			"OneChat Message", {"bulk_message_reference": row.name, "status": "sent"}
		)

		row["failed_count"] = frappe.db.count(
			"OneChat Message", {"bulk_message_reference": row.name, "status": "failed"}
		)

	return data
