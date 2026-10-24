import json
import time
from contextlib import contextmanager

import frappe
import requests
from frappe import _
from frappe.utils import (
	add_days,
	cint,
	flt,
	fmt_money,
	now_datetime,
	nowdate,
	strip_html,
)

from onechat import integrations
from onechat.integrations import connection

ERP = connection.site("erpnext")
from onechat.inbox.conversations import CONTACT, MESSAGE, find_contact, guard, publish
from onechat.inbox.visibility import check as check_visible
from onechat.utils import get_whatsapp_account
from onechat.workspace.session import is_admin

ACCOUNT = "OneChat Account"
MAX_PRODUCTS = 30
SUMMARY_ITEMS = 12
NAME_LIMIT = 40
DELIVERY_DAYS = 7
BATCH_SIZE = 1000
OPEN_REQUESTS = ["Requested", "Initiated", "Partially Paid"]
CATALOG_FILTERS = "onechat:catalog:filters"
SELLABLE = {
	"is_sales_item": 1,
	"disabled": 0,
	"has_variants": 0,
	"image": ["is", "set"],
}


def enabled():
	return any(spec["name"] == "erpnext" for spec in integrations.active())


def catalog_ready():
	return frappe.get_meta(ACCOUNT).has_field("catalog_id")


def account_for(contact):
	name = contact.get("whatsapp_account") or frappe.db.get_value(
		MESSAGE,
		{"whatsapp_contact": contact.name, "whatsapp_account": ["is", "set"]},
		"whatsapp_account",
		order_by="creation desc",
	)
	if name:
		return name

	default = get_whatsapp_account(account_type="outgoing")
	return default.name if default else None


def catalog_of(account):
	if not account or not catalog_ready():
		return None

	return frappe.db.get_value(ACCOUNT, account, "catalog_id")


def has_catalog(contact):
	return bool(contact.mobile_no and catalog_of(account_for(contact)))


def chosen(account, fieldname):
	if not account or not frappe.get_meta(ACCOUNT).has_field(fieldname):
		return []
	value = frappe.db.get_value(ACCOUNT, account, fieldname)
	try:
		names = json.loads(value) if value else []
	except ValueError:
		return []
	return [name for name in names if isinstance(name, str) and name]


def with_children(doctype, names):
	if not names:
		return []
	source = ERP.source()
	out = set(names)
	for row in source.get_all(doctype, filters={"name": ["in", names]}, fields=["lft", "rgt"], limit=0):
		if row.get("lft") is None or row.get("rgt") is None:
			continue
		for child in source.get_all(
			doctype,
			filters={"lft": [">", row.get("lft")], "rgt": ["<", row.get("rgt")]},
			fields=["name"],
			limit=0,
		):
			out.add(child.get("name"))
	return sorted(out)


FILTER_TYPES = (
	"Data",
	"Select",
	"Link",
	"Check",
	"Int",
	"Float",
	"Currency",
	"Percent",
	"Date",
	"Datetime",
	"Small Text",
)
FILTER_OPERATORS = ("=", "!=", ">", "<", ">=", "<=", "like", "not like", "is")


def item_fields():
	source = ERP.source()
	rows = (
		source.meta_fields("Item")
		if source.remote
		else [field.as_dict() for field in frappe.get_meta("Item").fields]
	)
	fields = [
		{
			"fieldname": row.get("fieldname"),
			"label": row.get("label") or row.get("fieldname"),
			"fieldtype": (
				"Data" if source.remote and row.get("fieldtype") == "Link" else row.get("fieldtype")
			),
			"options": (row.get("options") if row.get("fieldtype") in ("Select", "Link") else None),
		}
		for row in rows
		if row.get("fieldname") and row.get("fieldtype") in FILTER_TYPES
	]
	return sorted(fields, key=lambda row: str(row["label"]).lower())


def custom_filters(account):
	if not account or not frappe.get_meta(ACCOUNT).has_field("catalog_item_filters"):
		return []
	value = frappe.db.get_value(ACCOUNT, account, "catalog_item_filters")
	try:
		rows = json.loads(value) if value else []
	except ValueError:
		return []
	allowed = None
	out = []
	for row in rows if isinstance(rows, list) else []:
		if not (isinstance(row, list) and len(row) == 3 and row[1] in FILTER_OPERATORS):
			continue
		if row[1] == "is" and row[2] not in ("set", "not set"):
			continue
		if allowed is None:
			allowed = {field["fieldname"] for field in item_fields()}
		if row[0] in allowed and isinstance(row[2], str | int | float):
			out.append(["Item", row[0], row[1], row[2]])
	return out


def item_filters(account):
	filters = [
		["Item", key, *(value if isinstance(value, list) else ["=", value])]
		for key, value in SELLABLE.items()
	]
	groups = with_children("Item Group", chosen(account, "catalog_item_groups"))
	brands = chosen(account, "catalog_brands")
	if groups:
		filters.append(["Item", "item_group", "in", groups])
	if brands:
		filters.append(["Item", "brand", "in", brands])
	return filters + custom_filters(account)


@frappe.whitelist()
def catalog_filters():
	if not is_admin():
		frappe.throw(_("Only OneChat admins can change the catalog."), frappe.PermissionError)
	cached = frappe.cache().get_value(CATALOG_FILTERS)
	if cached:
		return cached
	source = ERP.source()

	def names(doctype, filters=None):
		return [
			row.get("name")
			for row in source.get_all(doctype, filters=filters, fields=["name"], order_by="name asc", limit=0)
		]

	result = {
		"item_groups": names("Item Group"),
		"brands": names("Brand"),
		"warehouses": names("Warehouse", {"disabled": 0}),
		"price_lists": names("Price List", {"selling": 1, "enabled": 1}),
		"item_fields": item_fields(),
	}
	frappe.cache().set_value(CATALOG_FILTERS, result, expires_in_sec=600)
	return result


def price_list_for(account):
	price_list = (
		frappe.db.get_value(ACCOUNT, account, "commerce_price_list") if account and catalog_ready() else None
	)

	return price_list or ERP.source().single_value("Selling Settings", "selling_price_list")


def price_map(price_list, codes=None):
	if not price_list:
		return {}

	filters = {"price_list": price_list, "customer": ["is", "not set"]}
	if codes is not None:
		filters["item_code"] = ["in", codes or [""]]

	rows = ERP.source().get_all(
		"Item Price",
		filters=filters,
		fields=["item_code", "price_list_rate", "currency"],
		order_by="valid_from asc",
	)

	return {row.item_code: row for row in rows}


def absolute(path):
	return ERP.source().absolute(path)


def company():
	source = ERP.source()
	local = None if source.remote else frappe.defaults.get_user_default("Company")
	return (
		local
		or source.single_value("Global Defaults", "default_company")
		or (source.get_list("Company", limit=1) or [{}])[0].get("name")
	)


@frappe.whitelist()
def products(contact: str, search: str | None = None):
	guard()
	check_visible(contact)

	account = account_for(frappe.get_doc(CONTACT, contact))
	if not catalog_of(account):
		return []
	from onechat.whatsapp.catalog import catalog_page

	rows = catalog_page(frappe.get_doc(ACCOUNT, account), search).get("rows") or []
	return [
		{
			"item_code": row.get("retailer_id"),
			"item_name": row.get("name") or row.get("retailer_id"),
			"image": row.get("image_url"),
			"price": row.get("price"),
			"availability": row.get("availability"),
			"review_status": row.get("review_status"),
		}
		for row in rows
		if row.get("retailer_id")
	]


def send_products(contact, payload=None):
	payload = frappe.parse_json(payload or {})
	codes = list(dict.fromkeys(code for code in payload.get("items") or [] if code))
	if not codes:
		frappe.throw(_("Pick at least one product to send."))
	if len(codes) > MAX_PRODUCTS:
		frappe.throw(_("You can send up to {0} products at once.").format(MAX_PRODUCTS))

	account = account_for(contact)
	if not catalog_of(account):
		frappe.throw(_("Set a catalog ID on the WhatsApp account first."))

	header = (payload.get("header") or "").strip()
	body = (payload.get("body") or "").strip()
	names = item_names(codes)
	summary = ", ".join(names.get(code) or code for code in codes)
	frappe.get_doc(
		{
			"doctype": MESSAGE,
			"type": "Outgoing",
			"message_type": "Manual",
			"to": contact.mobile_no,
			"message": "\n".join([part for part in [body, _("Products: {0}").format(summary)] if part]),
			"content_type": "product" if len(codes) == 1 else "product_list",
			"source": "Agent",
			"products": frappe.as_json({"header": header, "body": body, "items": codes}),
			"whatsapp_account": account,
			"reference_doctype": CONTACT,
			"reference_name": contact.name,
		}
	).insert(ignore_permissions=True)

	return _("Product sent") if len(codes) == 1 else _("{0} products sent").format(len(codes))


def graph(account, path, method="POST", **kwargs):
	response = requests.request(
		method,
		f"{account.url}/{account.version}/{path}",
		headers={"Authorization": f"Bearer {account.get_password('token')}"},
		timeout=120,
		**kwargs,
	)
	try:
		body = response.json()
	except ValueError:
		body = {}
	if not response.ok:
		raise frappe.ValidationError((body.get("error") or {}).get("message") or response.text)

	return body


def item_link(code):
	source = ERP.source()
	if source.has_doctype("Website Item"):
		route = source.get_value("Website Item", {"item_code": code, "published": 1}, "route")
		if route:
			return absolute(f"/{route}")

	return absolute("/")


ERPNEXT_STOCK = "Use ERPNext stock"
PAGE = 500


def stock_map(codes, warehouses=None):
	stocked = {}
	for start in range(0, len(codes), BATCH_SIZE):
		chunk = codes[start : start + BATCH_SIZE]
		filters = {"item_code": ["in", chunk]}
		if warehouses:
			filters["warehouse"] = ["in", warehouses]
		for row in ERP.source().get_all(
			"Bin",
			filters=filters,
			fields=["item_code", "sum(actual_qty) as qty"],
			group_by="item_code",
			limit=0,
		):
			stocked[row.get("item_code")] = flt(row.get("qty"))
	return stocked


def catalog_ids(account):
	ids, after = [], None
	for page in range(200):
		params = {"fields": "retailer_id", "limit": PAGE}
		if after:
			params["after"] = after
		result = graph(account, f"{account.catalog_id}/products", "GET", params=params)
		ids += [row.get("retailer_id") for row in result.get("data") or [] if row.get("retailer_id")]
		paging = result.get("paging") or {}
		after = (paging.get("cursors") or {}).get("after")
		if not paging.get("next") or not after:
			break
	return ids


def erp_items(codes):
	known = set()
	for start in range(0, len(codes), BATCH_SIZE):
		chunk = codes[start : start + BATCH_SIZE]
		known.update(
			row.get("name")
			for row in ERP.source().get_all("Item", filters={"name": ["in", chunk]}, fields=["name"], limit=0)
		)
	return known


def removals(account, kept):
	listed = [code for code in catalog_ids(account) if code not in kept]
	return sorted(erp_items(listed)) if listed else []


KEEP_ORDERABLE = "Keep it orderable"
FOLLOW_NEGATIVE = "Follow ERPNext negative stock"


def empty_status(doc):
	mode = doc.get("catalog_when_out")
	if mode == KEEP_ORDERABLE:
		return "available for order"
	if mode == FOLLOW_NEGATIVE and cint(ERP.source().single_value("Stock Settings", "allow_negative_stock")):
		return "available for order"
	return "out of stock"


ITEM_DETAILS = "erpnext.stock.get_item_details.get_item_details"


def with_gst(account):
	if not account or not frappe.get_meta(ACCOUNT).has_field("catalog_with_gst"):
		return False
	return bool(cint(frappe.db.get_value(ACCOUNT, account, "catalog_with_gst")))


def item_details(source, code, company_name, price_list, currency):
	args = {
		"item_code": code,
		"company": company_name,
		"doctype": "Sales Order",
		"price_list": price_list,
		"selling_price_list": price_list,
		"currency": currency,
		"price_list_currency": currency,
		"conversion_rate": 1,
		"plc_conversion_rate": 1,
		"qty": 1,
		"transaction_date": nowdate(),
	}
	if source.remote:
		try:
			return source.call(ITEM_DETAILS, args=json.dumps(args)) or {}
		except connection.RemoteError:
			return source.call(ITEM_DETAILS, ctx=json.dumps(args)) or {}
	return frappe.get_attr(ITEM_DETAILS)(frappe._dict(args)) or {}


def template_rate(source, template):
	try:
		rate = source.get_value("Item Tax Template", template, "gst_rate")
	except Exception:
		rate = None
	if rate:
		return flt(rate)
	rows = (source.get_doc("Item Tax Template", template) or {}).get("taxes") or []
	igst = [row for row in rows if "igst" in str(row.get("tax_type") or "").lower()]
	if igst:
		return flt(igst[0].get("tax_rate"))
	return sum(flt(row.get("tax_rate")) for row in rows)


def gst_rates(account, codes):
	if not codes or not with_gst(account):
		return {}
	source = ERP.source()
	company_name = company()
	price_list = price_list_for(account)
	currency = source.get_value("Price List", price_list, "currency") if price_list else None
	templates, out = {}, {}
	for code in codes:
		try:
			details = item_details(source, code, company_name, price_list, currency)
		except Exception:
			frappe.log_error(title=f"OneChat catalog GST: {code}")
			continue
		template = details.get("item_tax_template")
		if not template:
			out[code] = 0
			continue
		if template not in templates:
			try:
				templates[template] = template_rate(source, template)
			except Exception:
				frappe.log_error(title=f"OneChat catalog GST template: {template}")
				templates[template] = 0
		out[code] = templates[template]
	return out


def catalog_item(item, price, brand, availability="in stock", gst=0):
	amount = flt(price.price_list_rate) * (1 + flt(gst) / 100)
	return {
		"id": item.item_code,
		"title": (item.item_name or item.item_code)[:150],
		"description": (strip_html(item.description or "").strip() or item.item_name or item.item_code)[
			:9999
		],
		"availability": availability,
		"condition": "new",
		"price": f"{amount:.2f} {price.currency}",
		"image_link": absolute(item.image),
		"link": item_link(item.item_code),
		"brand": (item.brand or brand)[:100],
	}


def batch_errors(account, handles):
	errors = []
	for handle in handles:
		for attempt in range(10):
			time.sleep(3)
			result = graph(
				account,
				f"{account.catalog_id}/check_batch_request_status",
				"GET",
				params={"handle": handle},
			)
			status = (result.get("data") or [{}])[0]
			if status.get("status") == "finished":
				errors += [
					f"{row.get('id') or row.get('line')}: {row.get('message')}"
					for row in status.get("errors") or []
				]
				break

	return errors


def nightly_sync():
	if not enabled() or not catalog_ready():
		return
	for account in frappe.get_all(
		ACCOUNT,
		filters={
			"catalog_id": ["is", "set"],
			"status": "Active",
			"catalog_auto_sync": 1,
		},
		pluck="name",
	):
		frappe.enqueue(
			"onechat.integrations.erpnext_commerce.sync_catalog",
			queue="long",
			timeout=3600,
			job_id=f"onechat_catalog_{account}",
			deduplicate=True,
			account=account,
		)


@frappe.whitelist(methods=["POST"])
def start_sync(account: str):
	if not is_admin():
		frappe.throw(_("Only OneChat admins can sync the catalog."), frappe.PermissionError)
	if not enabled():
		frappe.throw(_("Turn on the ERPNext integration to sync items."))
	if not catalog_of(account):
		frappe.throw(_("Add a catalog ID and save the account first."))

	frappe.db.set_value(ACCOUNT, account, "catalog_sync_status", _("Sync in progress"))
	frappe.enqueue(
		"onechat.integrations.erpnext_commerce.sync_catalog",
		queue="long",
		timeout=3600,
		job_id=f"onechat_catalog_{account}",
		deduplicate=True,
		account=account,
		user=frappe.session.user,
	)

	return _("Catalog sync started. This can take a few minutes.")


def sync_catalog(account, user=None):
	doc = frappe.get_doc(ACCOUNT, account)
	prices = price_map(price_list_for(account))
	brand = company() or frappe.local.site
	items = ERP.source().get_all(
		"Item",
		filters=item_filters(account),
		fields=[
			"item_code",
			"item_name",
			"description",
			"image",
			"brand",
			"is_stock_item",
		],
	)
	use_stock = doc.get("catalog_stock") == ERPNEXT_STOCK
	warehouses = with_children("Warehouse", chosen(account, "catalog_warehouses")) if use_stock else []
	stock = (
		stock_map(
			[item.item_code for item in items if cint(item.get("is_stock_item"))],
			warehouses,
		)
		if use_stock
		else {}
	)
	when_empty = empty_status(doc) if use_stock else "out of stock"

	priced = [
		item.item_code
		for item in items
		if prices.get(item.item_code) and flt(prices[item.item_code].price_list_rate)
	]
	gst = gst_rates(account, priced)
	batch, skipped, errors, kept, sold_out = [], [], [], set(), 0
	for item in items:
		price = prices.get(item.item_code)
		if not price or not flt(price.price_list_rate):
			skipped.append(item.item_code)
			continue
		available = not use_stock or not cint(item.get("is_stock_item")) or stock.get(item.item_code, 0) > 0
		sold_out += 0 if available else 1
		kept.add(item.item_code)
		batch.append(
			{
				"method": "UPDATE",
				"data": catalog_item(
					item,
					price,
					brand,
					"in stock" if available else when_empty,
					gst.get(item.item_code),
				),
			}
		)

	try:
		gone = removals(doc, kept)
	except Exception as error:
		gone = []
		errors.append(_("Could not check the catalog for old items: {0}").format(str(error)))
		frappe.log_error(title="OneChat catalog cleanup")
	batch += [{"method": "DELETE", "data": {"id": code}} for code in gone]

	for start in range(0, len(batch), BATCH_SIZE):
		chunk = batch[start : start + BATCH_SIZE]
		try:
			result = graph(
				doc,
				f"{doc.catalog_id}/items_batch",
				json={
					"item_type": "PRODUCT_ITEM",
					"allow_upsert": True,
					"requests": chunk,
				},
			)
			errors += batch_errors(doc, result.get("handles") or [])
		except Exception as error:
			errors.append(_("{0} items failed: {1}").format(len(chunk), str(error)))
			frappe.log_error(title="OneChat catalog sync")

	lines = [
		_(
			"{0} items sent, {1} without stock ({2}), {3} removed, {4} skipped without a price, {5} errors"
		).format(len(kept), sold_out, _(when_empty), len(gone), len(skipped), len(errors))
	]
	if gone:
		lines.append(_("Removed: {0}").format(", ".join(gone[:20])))
	if skipped:
		lines.append(_("Skipped: {0}").format(", ".join(skipped[:20])))
	lines += errors[:20]
	status = "\n".join(lines)

	frappe.db.set_value(
		ACCOUNT,
		account,
		{"catalog_last_synced": now_datetime(), "catalog_sync_status": status},
	)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit - background sync updates status before realtime event
	frappe.publish_realtime("onechat_catalog_sync", {"account": account, "status": status}, user=user)


def item_rows(codes):
	if not codes or not ERP.ready():
		return {}

	try:
		rows = ERP.source().get_all(
			"Item",
			or_filters={"name": ["in", codes], "item_code": ["in", codes]},
			fields=["name", "item_code", "item_name", "image"],
		)
	except connection.RemoteError:
		return {}
	found = {}
	for row in rows:
		for key in (row.get("name"), row.get("item_code")):
			if key in codes:
				found.setdefault(key, row)
	return found


def item_names(codes):
	return {code: row.item_name for code, row in item_rows(codes).items() if row.get("name") == code}


def public_image(item):
	image = (item or {}).get("image")
	return absolute(image) if image and "/private/" not in image else None


PAY = "OneChat WhatsApp Payment"


def payment_asks(source, orders, invoices):
	owner = {name: name for name in orders}
	for order, rows in invoices.items():
		for row in rows:
			owner[row.get("name")] = order
	if not owner:
		return {}
	asked = {}
	for row in source.get_all(
		"Payment Request",
		filters={"reference_name": ["in", list(owner)], "docstatus": 1, "status": ["in", OPEN_REQUESTS]},
		fields=["reference_name"],
	):
		asked[owner.get(row.get("reference_name"))] = _("Payment link sent")
	if frappe.db.table_exists(PAY):
		for name in frappe.get_all(
			PAY, filters={"reference_name": ["in", list(owner)], "status": "Pending"}, pluck="reference_name"
		):
			asked[owner.get(name)] = _("Asked on WhatsApp")
	return asked


def step(key, label, state, detail=None, url=None):
	return {"key": key, "label": label, "state": state, "detail": detail, "url": url}


def journey(source, order, invoices, asked):
	from onechat.insights.orders import invoice_paid, payment_state

	steps = [step("ordered", _("Order received"), "done")]
	if not order:
		steps.append(step("sales_order", _("Sales Order"), "todo", _("Not created")))
		return steps

	name, docstatus, currency = order.get("name"), cint(order.get("docstatus")), order.get("currency")
	steps.append(
		step(
			"sales_order",
			_("Sales Order"),
			"failed" if docstatus == 2 else "done" if docstatus == 1 else "partial",
			f"{name} · {_(order.get('status') or 'Draft')}",
			source.absolute(f"/app/sales-order/{name}"),
		)
	)
	if docstatus == 2:
		return steps

	rows = invoices.get(name) or []
	total = flt(order.get("grand_total"))
	paid = max(flt(order.get("advance_paid")), invoice_paid(rows))
	state = payment_state(order, paid) if docstatus == 1 else "Unpaid"
	if state == "Paid":
		steps.append(
			step("payment", _("Payment"), "done", _("{0} paid").format(fmt_money(paid, currency=currency)))
		)
	elif state == "Part paid":
		steps.append(
			step(
				"payment",
				_("Payment"),
				"partial",
				_("{0} of {1} paid").format(
					fmt_money(paid, currency=currency), fmt_money(total, currency=currency)
				),
			)
		)
	else:
		steps.append(step("payment", _("Payment"), "todo", asked.get(name) or _("Not paid")))

	billed = flt(order.get("per_billed"))
	steps.append(
		step(
			"invoice",
			_("Invoice"),
			"done" if billed >= 100 else "partial" if rows else "todo",
			", ".join(row.get("name") for row in rows) or _("Not invoiced"),
			source.absolute(f"/app/sales-invoice/{rows[0].get('name')}") if rows else None,
		)
	)

	delivered = flt(order.get("per_delivered"))
	steps.append(
		step(
			"delivery",
			_("Delivery"),
			"done" if delivered >= 100 else "partial" if delivered else "todo",
			_("Delivered")
			if delivered >= 100
			else _("{0}% delivered").format(f"{delivered:g}")
			if delivered
			else _("Not delivered"),
		)
	)
	return steps


def journeys(message_ids):
	if not message_ids or not enabled() or not ERP.ready():
		return {}
	from onechat.insights.orders import invoices_by_order, sales_orders

	source = ERP.source()
	try:
		linked = sales_orders(source, message_ids)
		live = [row.get("name") for row in linked.values() if cint(row.get("docstatus")) == 1]
		invoices = invoices_by_order(source, live) if live else {}
	except Exception:
		frappe.log_error(title="OneChat order journey")
		return {}
	try:
		asked = payment_asks(source, live, invoices)
	except Exception:
		frappe.log_error(title="OneChat order journey: payment requests")
		asked = {}
	return {key: journey(source, linked.get(key), invoices, asked) for key in message_ids}


def linked_orders(doc):
	refs = [(doc.get("reference_doctype"), doc.get("reference_name"))]
	refs += [(row.get("reference_doctype"), row.get("reference_name")) for row in doc.get("references") or []]
	names = {name for doctype, name in refs if doctype == "Sales Order" and name}
	invoices = [name for doctype, name in refs if doctype == "Sales Invoice" and name]
	if doc.doctype == "Sales Order":
		names.add(doc.name)
	elif doc.doctype == "Sales Invoice":
		invoices.append(doc.name)
	elif doc.doctype == "Delivery Note":
		names |= {
			row.get("against_sales_order") for row in doc.get("items") or [] if row.get("against_sales_order")
		}
	if invoices and frappe.db.table_exists("Sales Invoice Item"):
		names |= set(
			frappe.get_all(
				"Sales Invoice Item",
				filters={"parent": ["in", invoices], "sales_order": ["is", "set"]},
				pluck="sales_order",
			)
		)
	return names


def refresh_order_cards(doc, method=None):
	try:
		orders = linked_orders(doc)
		if not orders or not frappe.db.table_exists("Sales Order"):
			return
		ids = frappe.get_all(
			"Sales Order", filters={"name": ["in", list(orders)], "po_no": ["is", "set"]}, pluck="po_no"
		)
		messages = (
			frappe.get_all(
				MESSAGE,
				filters={
					"message_id": ["in", ids],
					"content_type": "order",
					"whatsapp_contact": ["is", "set"],
				},
				fields=["name", "whatsapp_contact"],
			)
			if ids
			else []
		)
		if messages:
			frappe.enqueue(
				"onechat.integrations.erpnext_commerce.publish_orders",
				queue="short",
				enqueue_after_commit=True,
				messages=messages,
			)
	except Exception:
		frappe.log_error(title=f"OneChat order card refresh: {doc.name}")


def publish_orders(messages):
	for row in messages:
		publish(row["whatsapp_contact"], row["name"])


CATALOG_ITEM = "onechat:catalog-item"
CATALOG_ITEM_TTL = 6 * 3600


def catalog_items(orders, codes):
	from onechat.whatsapp.catalog import attempt

	wanted = {}
	for order in orders:
		for row in order.get("product_items") or []:
			if order.get("catalog_id") and row.get("product_retailer_id") in codes:
				wanted.setdefault(order["catalog_id"], set()).add(row["product_retailer_id"])

	cache, found = frappe.cache(), {}
	for catalog_id, ids in wanted.items():
		missing = []
		for code in ids:
			hit = cache.get_value(f"{CATALOG_ITEM}:{catalog_id}:{code}")
			if hit is None:
				missing.append(code)
			else:
				found[code] = hit
		account = missing and frappe.db.get_value(ACCOUNT, {"catalog_id": catalog_id}, "name")
		if not account:
			continue
		body, error = attempt(
			frappe.get_doc(ACCOUNT, account),
			"GET",
			f"{catalog_id}/products",
			{
				"fields": "retailer_id,name,image_url",
				"filter": json.dumps({"retailer_id": {"is_any": missing}}),
				"limit": len(missing),
			},
		)
		if error:
			continue
		rows = {
			row.get("retailer_id"): {"name": row.get("name"), "image": row.get("image_url")}
			for row in body.get("data") or []
		}
		for code in missing:
			found[code] = rows.get(code) or {}
			cache.set_value(
				f"{CATALOG_ITEM}:{catalog_id}:{code}", found[code], expires_in_sec=CATALOG_ITEM_TTL
			)
	return found


def order_cards(messages):
	orders = {}
	for message in messages:
		try:
			orders[message.name] = frappe.parse_json(message.products) or {}
		except ValueError:
			continue
	codes = list(
		{
			row.get("product_retailer_id")
			for order in orders.values()
			for row in order.get("product_items") or []
			if row.get("product_retailer_id")
		}
	)
	items = item_rows(codes)
	bare = [code for code in codes if not public_image(items.get(code))]
	try:
		listed = catalog_items(orders.values(), bare) if bare else {}
	except Exception:
		frappe.log_error(title="OneChat order card: catalog items")
		listed = {}
	flows = journeys([message.message_id for message in messages if message.message_id])
	cards = {}
	for message in messages:
		if message.name not in orders:
			continue
		order, lines, total, count, currency = orders[message.name], [], 0, 0, None
		for row in order.get("product_items") or []:
			code = row.get("product_retailer_id")
			qty, price = flt(row.get("quantity")) or 1, flt(row.get("item_price"))
			currency = row.get("currency") or currency
			total += qty * price
			count += qty
			item, listing = items.get(code) or {}, listed.get(code) or {}
			lines.append(
				{
					"code": code,
					"name": item.get("item_name") or listing.get("name") or code,
					"image": public_image(item) or listing.get("image"),
					"qty": f"{qty:g}",
					"price": fmt_money(price, currency=currency),
					"amount": fmt_money(qty * price, currency=currency),
				}
			)
		cards[message.name] = {
			"items": lines,
			"count": f"{count:g}",
			"total": fmt_money(total, currency=currency),
			"note": order.get("text"),
			"journey": flows.get(message.message_id),
		}
	return cards


def order_details(order):
	rows = (order or {}).get("product_items") or []
	names = item_names([row.get("product_retailer_id") for row in rows if row.get("product_retailer_id")])
	items, total, currency = [], 0, None
	for row in rows:
		qty, price = flt(row.get("quantity")) or 1, flt(row.get("item_price"))
		currency = row.get("currency") or currency
		total += qty * price
		code = row.get("product_retailer_id")
		items.append(
			{
				"item_code": code,
				"item_name": names.get(code) or code,
				"known": code in names,
				"qty": qty,
				"rate": price,
				"amount": qty * price,
			}
		)

	lines = [item_line(row, currency, NAME_LIMIT) for row in items[:SUMMARY_ITEMS]]
	if len(items) > SUMMARY_ITEMS:
		lines.append(_("+ {0} more items").format(len(items) - SUMMARY_ITEMS))
	return {
		"items": items,
		"summary": "\n".join(lines),
		"count": len(items),
		"quantity": sum(row["qty"] for row in items),
		"total": total,
		"currency": currency,
		"note": (order or {}).get("text") or "",
		"unknown": [row["item_code"] for row in items if names and not row["known"]],
	}


def item_line(row, currency, limit=None):
	name = row["item_name"] or ""
	if limit and len(name) > limit:
		name = name[: limit - 1] + "…"
	return f"{row['qty']:g} × {name} · {fmt_money(row['rate'], currency=currency)}"


def order_summary(order):
	details = order_details(order)
	currency = details["currency"]
	lines = [_("New order ({0} items)").format(details["count"])]
	lines += [item_line(row, currency) for row in details["items"]]
	lines.append(_("Total: {0}").format(fmt_money(details["total"], currency=currency)))
	if details["note"]:
		lines.append(_("Note: {0}").format(details["note"]))

	return "\n".join(lines)


def customer_for(contact):
	from onechat.integrations import links

	contact = links.view(contact, "erpnext")
	if contact.reference_doctype == "Customer" and contact.reference_docname:
		return contact.reference_docname

	from onechat.integrations.erpnext import create_customer

	relink = not contact.reference_docname or contact.reference_doctype == "Lead"
	name = None
	if contact.reference_doctype == "Lead" and contact.reference_docname:
		name = ERP.source().get_value("Customer", {"lead_name": contact.reference_docname}, "name")
	if not name:
		name = create_customer(contact, ignore_permissions=True)[1]
	if relink:
		links.add(contact.name, "Customer", name, main=True)
		publish(contact.name)

	return name


def create_sales_order(message, extra=None, submit=False, days=None, item_extra=None):
	order = frappe.parse_json(message.products or "{}") or {}
	source = ERP.source()
	codes = [
		row.get("product_retailer_id")
		for row in order.get("product_items") or []
		if row.get("product_retailer_id")
	]
	known = set(item_names(codes))
	rows = [row for row in order.get("product_items") or [] if row.get("product_retailer_id") in known]
	contact = message.get("whatsapp_contact") or find_contact(message.get("from"))
	if not rows or not contact:
		return None

	customer = customer_for(frappe.get_doc(CONTACT, contact))
	currency = next((row.get("currency") for row in rows if row.get("currency")), None)
	gst = gst_rates(message.whatsapp_account, [row["product_retailer_id"] for row in rows])
	price_list = price_list_for(message.whatsapp_account)
	delivery = add_days(nowdate(), DELIVERY_DAYS if days in (None, "") else cint(days))
	values = frappe._dict(
		{
			"doctype": "Sales Order",
			"customer": customer,
			"company": company(),
			"order_type": "Sales",
			"transaction_date": nowdate(),
			"delivery_date": delivery,
			"po_no": message.message_id,
			"ignore_pricing_rule": 1,
			"items": [
				{
					"item_code": row["product_retailer_id"],
					"qty": flt(row.get("quantity")) or 1,
					"rate": flt(
						flt(row.get("item_price")) / (1 + flt(gst.get(row["product_retailer_id"])) / 100),
						2,
					),
					"delivery_date": delivery,
					**(item_extra or {}),
				}
				for row in rows
			],
		}
	)
	if currency and source.exists("Currency", currency):
		values.currency = currency
	if price_list:
		values.selling_price_list = price_list
	values.update(extra or {})
	if source.remote:
		doc = source.insert(values)
		return source.submit(doc).name if submit else doc.name

	so = frappe.get_doc(values)
	so.set_missing_values()
	so.insert(ignore_permissions=True)
	if submit:
		so.submit()

	return so.name


def order_of(message):
	if not message.get("message_id"):
		return None
	return ERP.source().get_value("Sales Order", {"po_no": message.message_id, "docstatus": ["<", 2]}, "name")


@contextmanager
def elevated():
	user = frappe.session.user
	if not ERP.is_remote():
		frappe.set_user("Administrator")
	try:
		yield
	finally:
		frappe.set_user(user)


def mark_order(message, order, submitted=False):
	label = _("Sales Order {0} created") if submitted else _("Draft Sales Order {0} created")
	text = "\n".join([message.message or "", label.format(order)])
	frappe.db.set_value(MESSAGE, message.name, "message", text, update_modified=False)
	if message.get("whatsapp_contact"):
		publish(message.whatsapp_contact, message.name)


def handle_order(message):
	if not enabled() or (message.get("flags") or {}).get("onechat_order_flow"):
		return

	frappe.db.savepoint("onechat_order")
	try:
		with elevated():
			order = create_sales_order(message)
	except Exception:
		frappe.db.rollback(save_point="onechat_order")
		frappe.log_error(title="OneChat WhatsApp order")
		return

	if order:
		mark_order(message, order)


def can_request_payment(contact, doctype, name):
	if doctype != "Sales Invoice" or contact.reference_doctype != "Customer" or not contact.mobile_no:
		return False

	row = ERP.source().get_value(doctype, name, ["customer", "docstatus", "outstanding_amount"])

	return (
		bool(row)
		and row.customer == contact.reference_docname
		and row.docstatus == 1
		and flt(row.outstanding_amount) > 0
	)


def payment_url(invoice):
	source = ERP.source()
	existing = source.get_all(
		"Payment Request",
		filters={
			"reference_doctype": invoice.doctype,
			"reference_name": invoice.name,
			"docstatus": 1,
			"status": ["in", OPEN_REQUESTS],
			"payment_url": ["is", "set"],
		},
		fields=["payment_url"],
		order_by="creation desc",
		limit=1,
	)
	if existing:
		return existing[0].payment_url

	if source.remote:
		request = source.call(
			"erpnext.accounts.doctype.payment_request.payment_request.make_payment_request",
			dt=invoice.doctype,
			dn=invoice.name,
			party_type="Customer",
			party=invoice.customer,
			submit_doc=1,
			mute_email=1,
			return_doc=1,
		)
		if request and request.get("docstatus") == 0:
			request = source.submit(request)
		return (request or {}).get("payment_url")

	from erpnext.accounts.doctype.payment_request.payment_request import (
		make_payment_request,
	)

	request = make_payment_request(
		dt=invoice.doctype,
		dn=invoice.name,
		party_type="Customer",
		party=invoice.customer,
		submit_doc=1,
		mute_email=1,
		return_doc=1,
	)
	if request.docstatus == 0:
		request.flags.mute_email = True
		request.submit()

	return request.payment_url


def send_text(contact, text, reference=None, reply_to=None):
	frappe.get_doc(
		{
			"doctype": MESSAGE,
			"type": "Outgoing",
			"message_type": "Manual",
			"to": contact.mobile_no,
			"message": text,
			"content_type": "text",
			"whatsapp_account": account_for(contact),
			"reference_doctype": reference[0] if reference else CONTACT,
			"reference_name": reference[1] if reference else contact.name,
			"is_reply": 1 if reply_to else 0,
			"reply_to_message_id": reply_to,
		}
	).insert(ignore_permissions=True)


def send_payment_link(contact, doctype, name):
	source = ERP.source()
	invoice = source.get_doc(doctype, name)
	gateway = _("Set up a payment gateway in ERPNext to send payment links.")
	if not source.exists("Payment Gateway Account", {"company": invoice.company, "is_default": 1}):
		frappe.throw(gateway)

	url = payment_url(invoice)
	if not url:
		frappe.throw(gateway)

	amount = fmt_money(invoice.outstanding_amount, currency=invoice.currency)
	send_text(
		contact,
		_("Invoice {0} for {1} is due. Pay securely here: {2}").format(invoice.name, amount, url),
	)

	return _("Payment link sent")


def payment_update(doc, method=None, *args):
	if "erpnext" not in frappe.get_installed_apps():
		return

	if method == "on_payment_authorized":
		paid = (args[0] if args else None) in ("Authorized", "Completed")
		if paid:
			settle(doc)
	else:
		paid = doc.status == "Paid" and doc.has_value_changed("status")
	if paid:
		request_paid(doc)
	from onechat.integrations.payments import request_changed

	request_changed(doc)


def request_paid(doc):
	payment_received(doc)
	from onechat.integrations.payments import alert_request

	alert_request(doc)
	try:
		from onechat.integrations.payments import cancel_requests
		from onechat.whatsapp.pay import cancel_open

		cancel_requests(
			doc.get("reference_doctype"),
			doc.get("reference_name"),
			keep=doc.get("name"),
		)
		cancel_open(doc.get("reference_doctype"), doc.get("reference_name"))
	except Exception:
		frappe.log_error(title="OneChat payment clean-up")


def entry_requests(doc):
	return list(
		dict.fromkeys(
			row.get("payment_request") for row in doc.get("references") or [] if row.get("payment_request")
		)
	)


def entry_submitted(doc, method=None):
	if "erpnext" not in frappe.get_installed_apps():
		return
	from onechat.integrations.payments import request_changed

	for name in entry_requests(doc):
		try:
			request = frappe.get_doc("Payment Request", name)
			if request.status == "Paid":
				request_paid(request)
			request_changed(request)
		except Exception:
			frappe.log_error(title=f"OneChat payment entry {doc.get('name')}")


def remote_entry(doc):
	from onechat.integrations.payments import alert_request, refresh_links

	source = ERP.source()
	for name in entry_requests(doc):
		try:
			request = frappe._dict(source.get_doc("Payment Request", name) or {})
			if request.get("status") == "Paid":
				payment_received(request)
				alert_request(request)
			refresh_links(name)
		except Exception:
			frappe.log_error(title=f"OneChat payment entry {doc.get('name')}")


def settle(doc):
	if frappe.db.get_value("Payment Request", doc.name, "status") == "Paid":
		return
	try:
		mark_request_paid(doc)
	except Exception:
		frappe.log_error(title=f"OneChat payment entry for {doc.name}")


def mark_request_paid(doc):
	user = frappe.session.user
	try:
		frappe.set_user("Administrator")
		doc.flags.ignore_permissions = True
		return doc.set_as_paid()
	finally:
		frappe.set_user(user)


def payment_received(doc):
	if doc.get("party_type") != "Customer" or not doc.get("party"):
		return

	remote = ERP.is_remote()
	key = f"onechat:receipt:{doc.get('name')}"
	try:
		if remote and frappe.cache().get_value(key):
			return
		if not remote and frappe.db.exists(
			MESSAGE,
			{
				"reference_doctype": doc.get("doctype"),
				"reference_name": doc.get("name"),
			},
		):
			return

		from onechat.integrations.payments import link_messages

		name = next(
			(row.whatsapp_contact for row in link_messages(doc.get("name")) if row.whatsapp_contact),
			None,
		)
		name = name or frappe.db.get_value(
			CONTACT,
			{"reference_doctype": "Customer", "reference_docname": doc.get("party")},
		)
		if not name:
			return

		contact = frappe.get_doc(CONTACT, name)
		if not contact.mobile_no:
			return

		from onechat.integrations.payments import receipt

		receipt(contact, doc)
		if remote:
			frappe.cache().set_value(key, 1, expires_in_sec=90 * 86400)
	except Exception:
		frappe.log_error(title="OneChat payment receipt")
