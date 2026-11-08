import frappe
from frappe import _
from frappe.utils import cint

from onechat.assistant.tools import Tool, ToolError
from onechat.assistant.tools.records import required, schema
from onechat.integrations import connection

CONTACT = "OneChat Contact"
ROWS = 5
ITEM_LIMIT = 10
MAX_ITEMS = 20
CLOSED = ["Completed", "Closed", "Cancelled"]
SECTIONS = (
	(
		"open_orders",
		"Sales Order",
		"customer",
		{"docstatus": 1, "status": ["not in", CLOSED]},
		[
			"name",
			"transaction_date",
			"delivery_date",
			"grand_total",
			"status",
			"per_delivered",
			"per_billed",
			"currency",
		],
		"transaction_date desc",
	),
	(
		"unpaid_invoices",
		"Sales Invoice",
		"customer",
		{"docstatus": 1, "outstanding_amount": [">", 0]},
		["name", "posting_date", "due_date", "grand_total", "outstanding_amount", "status", "currency"],
		"posting_date desc",
	),
	(
		"quotations",
		"Quotation",
		"party_name",
		{"docstatus": ["<", 2], "quotation_to": "Customer"},
		["name", "transaction_date", "valid_till", "grand_total", "status", "currency"],
		"transaction_date desc",
	),
	(
		"last_payments",
		"Payment Entry",
		"party",
		{"docstatus": 1, "party_type": "Customer"},
		["name", "posting_date", "paid_amount", "mode_of_payment"],
		"posting_date desc",
	),
)


def tolerant(fetch, default):
	try:
		return fetch()
	except (frappe.PermissionError, frappe.ValidationError):
		frappe.clear_last_message()
		return default


def contact_doc(call):
	if not call.contact:
		raise ToolError(_("Open the customer's chat first."))
	return frappe.get_doc(CONTACT, call.contact)


def customers(call):
	if call.get("customer"):
		return [call.get("customer")]
	from onechat.integrations.payments import customers_of

	found = customers_of(contact_doc(call))
	if not found:
		raise ToolError(_("This chat isn't linked to a customer yet. Say which customer."))
	return found


def section(names, doctype, party, filters, fields, order_by):
	source = connection.source_for(doctype)
	return tolerant(
		lambda: source.get_list(
			doctype,
			fields=fields,
			filters={**filters, party: ["in", names]},
			order_by=order_by,
			limit=ROWS,
		),
		[],
	)


def customer_overview(call):
	names = customers(call)
	details = tolerant(
		lambda: connection.source_for("Customer").get_list(
			"Customer",
			fields=["name", "customer_name", "customer_group", "territory", "mobile_no", "email_id"],
			filters={"name": ["in", names]},
			limit=len(names),
		),
		[{"name": name} for name in names],
	)
	out = {"customers": details}
	for key, doctype, party, filters, fields, order_by in SECTIONS:
		out[key] = section(names, doctype, party, filters, fields, order_by)
	return out


def selling_price_list(source):
	return (
		tolerant(lambda: source.single_value("Selling Settings", "selling_price_list"), None)
		or "Standard Selling"
	)


def prices_of(codes):
	source = connection.source_for("Item Price")
	rows = tolerant(
		lambda: source.get_list(
			"Item Price",
			fields=["item_code", "price_list_rate", "currency"],
			filters={"price_list": selling_price_list(source), "item_code": ["in", codes]},
			limit=len(codes) * 2,
		),
		[],
	)
	return {
		row.get("item_code"): f"{row.get('price_list_rate')} {row.get('currency') or ''}".strip()
		for row in rows
	}


def stock_of(codes):
	source = connection.source_for("Bin")
	rows = tolerant(
		lambda: source.get_list(
			"Bin",
			fields=["item_code", "sum(actual_qty) as qty"],
			filters={"item_code": ["in", codes]},
			group_by="item_code",
			order_by="item_code asc",
			limit=len(codes),
		),
		[],
	)
	return {row.get("item_code"): row.get("qty") for row in rows}


def find_items(call):
	text = required(call, "text")
	source = connection.source_for("Item")
	rows = source.get_list(
		"Item",
		fields=["name", "item_name", "stock_uom", "is_stock_item"],
		filters={"disabled": 0, "is_sales_item": 1},
		or_filters=[["name", "like", f"%{text}%"], ["item_name", "like", f"%{text}%"]],
		order_by="item_name asc",
		limit=min(cint(call.get("limit")) or ITEM_LIMIT, MAX_ITEMS),
	)
	codes = [row.get("name") for row in rows]
	prices = prices_of(codes) if codes else {}
	stock = stock_of(codes) if codes else {}
	return [
		{
			"item_code": row.get("name"),
			"item_name": row.get("item_name"),
			"uom": row.get("stock_uom"),
			"price": prices.get(row.get("name")),
			"in_stock": stock.get(row.get("name"), 0) if cint(row.get("is_stock_item")) else None,
		}
		for row in rows
	]


def what_customer_owes(call):
	from onechat.integrations.payments import payable

	rows = payable(contact_doc(call))
	return {"count": len(rows), "documents": rows}


def send_payment_link(call):
	from onechat.integrations import payments

	doctype = required(call, "doctype")
	name = required(call, "name")
	contact = contact_doc(call)
	if not payments.can_link(contact, doctype, name):
		raise ToolError(
			_(
				"{0} {1} can't get a payment link here. It must belong to this customer, be submitted and still due."
			).format(doctype, name)
		)
	return payments.send_link(contact, doctype, name)


CUSTOMER = {
	"type": "string",
	"description": "Customer name. Leave empty to use the customer linked to this chat.",
}

TOOLS = [
	Tool(
		name="customer_overview",
		description="One summary of a customer: details, open Sales Orders, unpaid Sales Invoices, recent \
Quotations and last payments. Start here for questions about a customer.",
		schema=schema({"customer": CUSTOMER}),
		handler=customer_overview,
		needs=("erpnext",),
	),
	Tool(
		name="find_items",
		description="Find sellable items by code or name, with their selling price and stock in hand. Use it \
to get exact item codes before creating a Quotation or Sales Order.",
		schema=schema(
			{
				"text": {"type": "string", "description": "Part of the item code or name."},
				"limit": {"type": "integer", "description": f"At most {MAX_ITEMS}. Default {ITEM_LIMIT}."},
			},
			["text"],
		),
		handler=find_items,
		needs=("erpnext",),
	),
	Tool(
		name="what_customer_owes",
		description="The invoices and orders the customer in this chat still has to pay, with the amount due.",
		schema=schema({}),
		handler=what_customer_owes,
		needs=("erpnext",),
		contact=True,
	),
	Tool(
		name="send_payment_link",
		description="Send the customer in this chat a secure payment link for one of their submitted Sales \
Invoices or Sales Orders. The user confirms first.",
		schema=schema(
			{
				"doctype": {"type": "string", "enum": ["Sales Invoice", "Sales Order"]},
				"name": {"type": "string", "description": "The invoice or order name."},
			},
			["doctype", "name"],
		),
		handler=send_payment_link,
		right="write",
		needs=("erpnext", "payments"),
		contact=True,
	),
]
