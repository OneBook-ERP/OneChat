import json
from collections import Counter, defaultdict

import frappe
from frappe.utils import flt, fmt_money

from onechat.workspace import numbers

MESSAGE = "OneChat Message"
CONTACT = "OneChat Contact"
ORDER = "Sales Order"
INVOICE = "Sales Invoice"
CHUNK = 200
TOP = 10
RECENT = 100
EPSILON = 0.01


def chunks(values):
	values = list(values)
	for start in range(0, len(values), CHUNK):
		yield values[start : start + CHUNK]


def lines_of(text):
	try:
		data = json.loads(text or "{}") or {}
	except ValueError:
		return []
	return [row for row in data.get("product_items") or [] if row.get("product_retailer_id")]


def line_value(row):
	return flt(row.get("item_price")) * (flt(row.get("quantity")) or 1)


def whatsapp_orders(span):
	filters = {"type": "Incoming", "content_type": "order", "creation": ["between", [span.since, span.until]]}
	hidden = numbers.hidden()
	if hidden:
		filters["whatsapp_account"] = ["not in", hidden]
	return frappe.get_all(
		MESSAGE,
		filters=filters,
		fields=["name", "message_id", "whatsapp_contact", "products", "creation"],
		order_by="creation desc",
		limit_page_length=0,
	)


def sales_orders(source, ids):
	found = {}
	for chunk in chunks(ids):
		for row in source.get_all(
			ORDER,
			filters={"po_no": ["in", chunk]},
			fields=[
				"name",
				"po_no",
				"status",
				"docstatus",
				"grand_total",
				"advance_paid",
				"per_billed",
				"currency",
				"creation",
			],
			order_by="creation asc",
		):
			current = found.get(row.get("po_no"))
			if not current or int(current.get("docstatus") or 0) == 2:
				found[row.get("po_no")] = row
	return found


def invoice_items(source, names):
	fields = ["parent", "sales_order"]
	rows = []
	for chunk in chunks(names):
		filters = {"sales_order": ["in", chunk], "docstatus": 1}
		if source.remote:
			rows += (
				source.call(
					"frappe.client.get_list",
					doctype=f"{INVOICE} Item",
					parent=INVOICE,
					fields=fields,
					filters=filters,
					limit_page_length=0,
				)
				or []
			)
		else:
			rows += frappe.get_all(f"{INVOICE} Item", filters=filters, fields=fields, limit_page_length=0)
	return rows


def invoiced_paid(source, names):
	try:
		items = invoice_items(source, names)
	except Exception:
		frappe.log_error(title="OneChat catalog orders: invoices")
		return {}
	by_order = defaultdict(set)
	for row in items:
		by_order[row.get("sales_order")].add(row.get("parent"))
	invoices = {}
	for chunk in chunks({name for names in by_order.values() for name in names}):
		for row in source.get_all(
			INVOICE, filters={"name": ["in", chunk]}, fields=["name", "grand_total", "outstanding_amount"]
		):
			invoices[row.get("name")] = flt(row.get("grand_total")) - flt(row.get("outstanding_amount"))
	return {order: sum(invoices.get(name, 0) for name in names) for order, names in by_order.items()}


def payment_state(order, paid):
	total = flt(order.get("grand_total"))
	if int(order.get("docstatus") or 0) != 1:
		return "Draft" if int(order.get("docstatus") or 0) == 0 else "Cancelled"
	if total and paid >= total - EPSILON:
		return "Paid"
	if paid > EPSILON:
		return "Part paid"
	return "Unpaid"


def money(value, currency):
	return fmt_money(value, currency=currency) if currency else f"{flt(value):,.2f}"


def report(span):
	from onechat.insights.metrics import picker, plot, slot
	from onechat.integrations.erpnext_commerce import ERP, enabled, item_names

	messages = whatsapp_orders(span)
	ready = enabled() and ERP.ready()
	source = ERP.source() if ready else None
	linked, paid_by_invoice, warning = {}, {}, None
	if source and not source.remote:
		from onechat.workspace.session import can_read

		if not can_read(ORDER):
			source, warning = (
				None,
				frappe._("Your role can't read Sales Orders, so orders aren't matched to ERPNext."),
			)
	if source and messages:
		try:
			linked = sales_orders(source, [row.message_id for row in messages if row.message_id])
			submitted = [
				row.get("name")
				for row in linked.values()
				if int(row.get("docstatus") or 0) == 1 and flt(row.get("per_billed"))
			]
			paid_by_invoice = invoiced_paid(source, submitted) if submitted else {}
		except Exception as error:
			frappe.log_error(title="OneChat catalog orders")
			warning = str(error)

	contacts = {
		row.name: row.contact_name or row.mobile_no
		for row in frappe.get_all(
			CONTACT,
			filters={
				"name": [
					"in",
					list({row.whatsapp_contact for row in messages if row.whatsapp_contact}) or [""],
				]
			},
			fields=["name", "contact_name", "mobile_no"],
		)
	}

	states = Counter()
	products = defaultdict(lambda: {"orders": 0, "qty": 0.0, "value": 0.0, "paid_value": 0.0})
	received, converted = defaultdict(Counter), defaultdict(Counter)
	totals = {"value": 0.0, "revenue": 0.0, "paid": 0.0}
	currency = None
	recent = []
	for message in messages:
		lines = lines_of(message.products)
		value = sum(line_value(row) for row in lines)
		currency = currency or next((row.get("currency") for row in lines if row.get("currency")), None)
		totals["value"] += value
		at = slot(message.creation, span.hourly)
		received[at]["count"] += 1
		order = linked.get(message.message_id)
		state, paid = "No order", 0.0
		if order:
			converted[at]["count"] += 1
			paid = max(flt(order.get("advance_paid")), paid_by_invoice.get(order.get("name"), 0.0))
			state = payment_state(order, paid)
			if state not in ("Draft", "Cancelled"):
				totals["revenue"] += flt(order.get("grand_total"))
				totals["paid"] += min(paid, flt(order.get("grand_total")))
		states[state] += 1
		for row in lines:
			product = products[row["product_retailer_id"]]
			product["orders"] += 1
			product["qty"] += flt(row.get("quantity")) or 1
			product["value"] += line_value(row)
			if state == "Paid":
				product["paid_value"] += line_value(row)
		if len(recent) < RECENT:
			recent.append(
				{
					"name": message.name,
					"contact": message.whatsapp_contact,
					"customer": contacts.get(message.whatsapp_contact) or message.whatsapp_contact,
					"creation": str(message.creation),
					"items": len(lines),
					"value": round(value, 2),
					"value_label": money(value, currency),
					"sales_order": order.get("name") if order else None,
					"sales_order_url": ERP.source().absolute(f"/app/sales-order/{order.get('name')}")
					if order
					else None,
					"order_status": order.get("status") if order else None,
					"state": state,
					"paid_label": money(paid, order.get("currency") or currency) if order else "",
				}
			)

	names = item_names(list(products)) if ready else {}
	ranked = sorted(
		(
			{
				"code": code,
				"name": names.get(code) or code,
				"orders": row["orders"],
				"qty": row["qty"],
				"value": round(row["value"], 2),
				"value_label": money(row["value"], currency),
				"paid_label": money(row["paid_value"], currency),
			}
			for code, row in products.items()
		),
		key=lambda row: row["value"],
		reverse=True,
	)

	count = len(messages)
	made = count - states["No order"]
	paid_count = states["Paid"]
	return {
		"ready": bool(ready),
		"warning": warning,
		"currency": currency,
		"summary": {
			"orders": count,
			"sales_orders": made,
			"conversion": round(made * 100 / count, 1) if count else None,
			"paid": paid_count,
			"paid_rate": round(paid_count * 100 / made, 1) if made else None,
			"value": round(totals["value"], 2),
			"value_label": money(totals["value"], currency),
			"revenue_label": money(totals["revenue"], currency),
			"paid_label": money(totals["paid"], currency),
		},
		"funnel": [
			{"stage": "WhatsApp orders", "count": count},
			{"stage": "Sales Orders", "count": made},
			{"stage": "Submitted", "count": made - states["Draft"] - states["Cancelled"]},
			{"stage": "Paid", "count": paid_count},
		],
		"states": [{"name": key, "value": value} for key, value in states.most_common() if value],
		"timeline": plot(span, orders=picker(received), sales_orders=picker(converted)),
		"products": ranked,
		"top_products": [{"name": row["name"], "value": row["value"]} for row in ranked[:TOP]],
		"recent": recent,
	}
