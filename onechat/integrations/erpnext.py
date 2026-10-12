import frappe
from frappe import _
from frappe.query_builder import Case
from frappe.utils import flt, fmt_money, formatdate
from pypika import CustomFunction
from pypika.terms import Field

from onechat.integrations import connection
from onechat.integrations.phone import frappe_phone

ERP = connection.site("erpnext")

LINKED = ("Customer", "Lead", "Supplier")

PHONE_FIELDS = {
	"Customer": ("mobile_no",),
	"Lead": ("whatsapp_no", "mobile_no", "phone"),
	"Supplier": ("mobile_no",),
}

THEMES = {
	"Completed": "green",
	"Paid": "green",
	"Submitted": "green",
	"Converted": "green",
	"Closed": "gray",
	"Draft": "gray",
	"Cancelled": "gray",
	"Overdue": "red",
	"Unpaid": "amber",
	"Partly Paid": "amber",
	"To Deliver and Bill": "blue",
	"To Bill": "blue",
	"To Deliver": "blue",
	"Open": "blue",
	"Replied": "blue",
	"Lead": "blue",
	"Opportunity": "blue",
	"Quotation": "blue",
	"Lost Quotation": "red",
	"Do Not Contact": "red",
}


def spec():
	return {
		"name": "erpnext",
		"label": "ERPNext",
		"app": "erpnext",
		"ready": "onechat.integrations.erpnext.ready",
		"setup": "erpnext",
		"sites_help": _(
			"On this site OneChat reads and writes ERPNext directly. On another site it connects over the Frappe REST API with Sign in (OAuth) or an API key, and adds signed webhooks there so flows can start from record changes. Payments and the Assistant follow this connection."
		),
		"icon": "lucide-building-2",
		"logo": "/assets/onechat/images/integrations/erpnext.svg",
		"category": _("ERP & CRM"),
		"docs_url": "https://docs.erpnext.com",
		"description": _(
			"Link WhatsApp contacts to customers, leads and suppliers, and see their orders, invoices and payments next to the chat."
		),
		"features": [
			_("Match new chats to customers, leads and suppliers by phone number"),
			_("See orders, invoices and payments beside the conversation"),
			_("Create a lead or customer from a chat in one click"),
			_("Send products from your catalog and payment links for unpaid invoices"),
			_("Start flows when a sales order, invoice or any other document changes"),
		],
		"link_doctypes": [
			{"doctype": "Customer", "label": _("Customers"), "icon": "lucide-briefcase", "theme": "green"},
			{"doctype": "Lead", "label": _("Leads"), "icon": "lucide-sprout", "theme": "blue"},
			{"doctype": "Supplier", "label": _("Suppliers"), "icon": "lucide-truck", "theme": "amber"},
		],
		"find_by_phone": "onechat.integrations.erpnext.find_by_phone",
		"find_all_by_phone": "onechat.integrations.erpnext.find_all_by_phone",
		"cards": "onechat.integrations.erpnext.cards",
		"stats": "onechat.integrations.erpnext.stats",
		"timeline": "onechat.integrations.erpnext.timeline",
		"metrics": "onechat.integrations.erpnext.metrics",
		"actions": [
			{
				"key": "create_lead",
				"needs": [("Lead", "create")],
				"label": _("Create lead"),
				"icon": "lucide-sprout",
				"method": "onechat.integrations.erpnext.create_lead",
				"condition": "onechat.integrations.erpnext.unlinked",
			},
			{
				"key": "create_customer",
				"needs": [("Customer", "create")],
				"label": _("Create customer"),
				"icon": "lucide-briefcase",
				"method": "onechat.integrations.erpnext.create_customer",
				"condition": "onechat.integrations.erpnext.unlinked_or_lead",
			},
			{
				"key": "request_payment",
				"needs": "onechat.integrations.payments.request_needs",
				"label": _("Request payment"),
				"icon": "lucide-credit-card",
				"dialog": "payment",
				"method": "onechat.integrations.payments.request_payment",
				"condition": "onechat.integrations.payments.has_payables",
			},
			{
				"key": "send_products",
				"needs": [("OneChat Message", "create")],
				"label": _("Send products"),
				"icon": "lucide-shopping-bag",
				"dialog": "products",
				"method": "onechat.integrations.erpnext_commerce.send_products",
				"condition": "onechat.integrations.erpnext_commerce.has_catalog",
			},
		],
		"row_actions": [
			{
				"key": "payment_link",
				"needs": [("OneChat Message", "create"), ("Payment Request", "create")],
				"label": _("Send payment link"),
				"icon": "lucide-credit-card",
				"method": "onechat.integrations.payments.send_link",
				"condition": "onechat.integrations.payments.can_link",
			},
		],
	}


RegexpReplace = CustomFunction("regexp_replace", ["value", "pattern", "replacement"])
RegexpReplaceAll = CustomFunction("regexp_replace", ["value", "pattern", "replacement", "flags"])


def digits(column):
	if frappe.db.db_type == "postgres":
		return RegexpReplaceAll(column, "[^0-9]", "", "g")

	return RegexpReplace(column, "[^0-9]", "")


def ready():
	return ERP.ready()


def find_by_phone(wa_number):
	if ERP.is_remote():
		return find_remote(wa_number)

	tail = f"%{wa_number[-10:]}"

	if frappe.db.table_exists("Contact Phone"):
		phone = frappe.qb.DocType("Contact Phone")
		link = frappe.qb.DocType("Dynamic Link")
		rank = Case()
		for index, doctype in enumerate(LINKED):
			rank = rank.when(link.link_doctype == doctype, index)

		match = (
			frappe.qb.from_(phone)
			.join(link)
			.on((link.parent == phone.parent) & (link.parenttype == "Contact"))
			.select(link.link_doctype, link.link_name)
			.where(digits(phone.phone).like(tail) & link.link_doctype.isin(LINKED))
			.orderby(rank)
			.limit(1)
			.run()
		)
		if match:
			return match[0][0], match[0][1]

	for doctype, fields in PHONE_FIELDS.items():
		meta = frappe.get_meta(doctype)
		table = frappe.qb.DocType(doctype)
		for field in fields:
			if not meta.has_field(field):
				continue
			name = (
				frappe.qb.from_(table)
				.select(table.name)
				.where(digits(Field(field, table=table)).like(tail))
				.limit(1)
				.run()
			)
			if name:
				return doctype, name[0][0]

	return None


MATCH_LIMIT = 10


def ranked(found):
	unique = list(dict.fromkeys(found))
	return sorted(unique, key=lambda pair: LINKED.index(pair[0]) if pair[0] in LINKED else len(LINKED))[
		:MATCH_LIMIT
	]


def find_all_by_phone(wa_number):
	if ERP.is_remote():
		return find_all_remote(wa_number)

	tail = f"%{wa_number[-10:]}"
	found = []
	if frappe.db.table_exists("Contact Phone"):
		phone = frappe.qb.DocType("Contact Phone")
		link = frappe.qb.DocType("Dynamic Link")
		found += [
			(row[0], row[1])
			for row in (
				frappe.qb.from_(phone)
				.join(link)
				.on((link.parent == phone.parent) & (link.parenttype == "Contact"))
				.select(link.link_doctype, link.link_name)
				.where(digits(phone.phone).like(tail) & link.link_doctype.isin(LINKED))
				.limit(MATCH_LIMIT * 2)
				.run()
			)
		]

	for doctype, fields in PHONE_FIELDS.items():
		meta = frappe.get_meta(doctype)
		table = frappe.qb.DocType(doctype)
		for field in fields:
			if not meta.has_field(field):
				continue
			found += [
				(doctype, row[0])
				for row in frappe.qb.from_(table)
				.select(table.name)
				.where(digits(Field(field, table=table)).like(tail))
				.limit(MATCH_LIMIT)
				.run()
			]

	return ranked(found)


def find_all_remote(wa_number):
	client = ERP.client()
	pattern = loose(wa_number)
	found = []
	for row in client.get_list(
		"Contact", fields=["name"], filters=[["Contact Phone", "phone", "like", pattern]], limit=MATCH_LIMIT
	):
		for link in client.get_doc("Contact", row.name).get("links") or []:
			if link.get("link_doctype") in LINKED:
				found.append((link["link_doctype"], link["link_name"]))

	for doctype, fields in PHONE_FIELDS.items():
		for field in fields:
			try:
				rows = client.get_list(
					doctype, fields=["name"], filters={field: ["like", pattern]}, limit=MATCH_LIMIT
				)
			except connection.RemoteError:
				continue
			found += [(doctype, row.name) for row in rows]

	return ranked(found)


def loose(wa_number):
	return "%" + "%".join(wa_number[-10:])


def find_remote(wa_number):
	client = ERP.client()
	pattern = loose(wa_number)
	contacts = client.get_list(
		"Contact", fields=["name"], filters=[["Contact Phone", "phone", "like", pattern]], limit=5
	)
	best = None
	for row in contacts:
		for link in client.get_doc("Contact", row.name).get("links") or []:
			if link.get("link_doctype") in LINKED:
				rank = LINKED.index(link["link_doctype"])
				if not best or rank < best[0]:
					best = (rank, link["link_doctype"], link["link_name"])
	if best:
		return best[1], best[2]

	for doctype, fields in PHONE_FIELDS.items():
		for field in fields:
			try:
				rows = client.get_list(doctype, fields=["name"], filters={field: ["like", pattern]}, limit=1)
			except connection.RemoteError:
				continue
			if rows:
				return doctype, rows[0].name

	return None


def route(doctype, name):
	return ERP.desk_url(doctype, name)


def theme(status):
	return THEMES.get(status, "gray")


def money(value, currency=None):
	return fmt_money(flt(value), currency=currency)


def cards(doctype, name):
	if doctype == "Customer":
		return customer_cards(name)
	if doctype == "Lead":
		return lead_cards(name)
	if doctype == "Supplier":
		return supplier_cards(name)

	return []


def summary(doctype, name, fields):
	doc = ERP.source().get_value(doctype, name, [field for field, _label in fields]) or {}

	return [{"label": label, "value": doc.get(field)} for field, label in fields if doc.get(field)]


def outstanding(doctype, party_field, name):
	rows = ERP.source().get_list(
		doctype,
		filters={party_field: name, "docstatus": 1},
		fields=["sum(outstanding_amount) as total", "currency"],
		group_by="currency",
	)

	return ", ".join(money(row.total, row.currency) for row in rows if flt(row.total))


def recent(doctype, filters, fields, title, subtitle, value, empty, view, actions=None):
	rows = ERP.source().get_list(doctype, filters=filters, fields=fields, order_by="creation desc", limit=5)

	return {
		"title": title,
		"icon": "lucide-list",
		"rows": [
			{
				"title": row.name,
				"subtitle": subtitle(row),
				"value": value(row),
				"status": row.get("status"),
				"theme": theme(row.get("status")),
				"url": route(doctype, row.name),
				"doctype": doctype,
				"name": row.name,
				"actions": actions(row) if actions else [],
			}
			for row in rows
		],
		"empty": empty,
		"url": ERP.base_url() + view if ERP.is_remote() else view,
	}


UNREGISTERED = ("Unregistered", "Consumer", "Overseas")


def record(doctype, name):
	try:
		return ERP.source().get_doc(doctype, name) or {}
	except Exception:
		frappe.log_error(title=f"OneChat {doctype} card")
		return {}


def gst_badge(doc):
	if doc.get("gstin"):
		return {"label": _("GST registered"), "theme": "green"}
	category = doc.get("gst_category")
	if category and category not in UNREGISTERED:
		return {"label": _(category), "theme": "blue"}
	if category or "gstin" in doc:
		return {"label": _("Not GST registered"), "theme": "gray"}
	return None


def filled(pairs):
	return [{"label": label, "value": value} for label, value in pairs if value not in (None, "")]


def sales_team(doc):
	rows = [row for row in doc.get("sales_team") or [] if row.get("sales_person")]
	if not rows:
		return None
	return {
		"title": _("Sales team"),
		"rows": [
			{
				"name": row.get("sales_person"),
				"detail": f"{flt(row.get('allocated_percentage')):g}%"
				if row.get("allocated_percentage")
				else "",
			}
			for row in rows
		],
	}


def order_due(row):
	if (
		row.docstatus != 1
		or row.status in ("Closed", "Completed", "Cancelled", "On Hold")
		or flt(row.get("per_billed")) >= 100
	):
		return False
	return (flt(row.get("rounded_total")) or flt(row.grand_total)) - flt(row.get("advance_paid")) > 0


def customer_cards(name):
	doc = record("Customer", name)
	kind = doc.get("customer_type")
	group = doc.get("customer_group")
	badges = [gst_badge(doc), {"label": _(kind), "theme": "gray"} if kind else None]
	fields = filled(
		[
			(_("GSTIN"), doc.get("gstin")),
			(_("Group"), group if group != kind else None),
			(_("Territory"), doc.get("territory")),
			(_("Account manager"), doc.get("account_manager")),
		]
	)
	due = outstanding("Sales Invoice", "customer", name)
	if due:
		fields.append({"label": _("Outstanding"), "value": due})

	return [
		{
			"title": _("Customer"),
			"icon": "lucide-briefcase",
			"headline": doc.get("customer_name") or name,
			"badges": [badge for badge in badges if badge],
			"fields": fields,
			"people": sales_team(doc),
			"url": route("Customer", name),
		},
		recent(
			"Sales Order",
			{"customer": name},
			[
				"name",
				"status",
				"docstatus",
				"transaction_date",
				"grand_total",
				"rounded_total",
				"advance_paid",
				"per_billed",
				"currency",
			],
			_("Recent orders"),
			lambda row: formatdate(row.transaction_date),
			lambda row: money(row.grand_total, row.currency),
			_("No orders yet"),
			f"/app/sales-order?customer={name}",
			lambda row: ["payment_link"] if order_due(row) else [],
		),
		recent(
			"Sales Invoice",
			{"customer": name, "docstatus": ["!=", 2]},
			["name", "status", "docstatus", "posting_date", "grand_total", "outstanding_amount", "currency"],
			_("Recent invoices"),
			lambda row: formatdate(row.posting_date),
			lambda row: money(row.grand_total, row.currency),
			_("No invoices yet"),
			f"/app/sales-invoice?customer={name}",
			lambda row: ["payment_link"] if row.docstatus == 1 and flt(row.outstanding_amount) > 0 else [],
		),
		recent(
			"Payment Entry",
			{"party_type": "Customer", "party": name, "docstatus": 1},
			[
				"name",
				"status",
				"posting_date",
				"paid_amount",
				"paid_from_account_currency as currency",
				"mode_of_payment",
			],
			_("Recent payments"),
			lambda row: " · ".join(
				[part for part in [formatdate(row.posting_date), row.mode_of_payment] if part]
			),
			lambda row: money(row.paid_amount, row.currency),
			_("No payments yet"),
			f"/app/payment-entry?party_type=Customer&party={name}",
		),
	]


def lead_cards(name):
	fields = summary(
		"Lead",
		name,
		[
			("status", _("Status")),
			("company_name", _("Company")),
			("source", _("Source")),
			("lead_owner", _("Owner")),
		],
	)
	headline = ERP.source().get_value("Lead", name, "lead_name") or name
	out = [
		{
			"title": _("Lead"),
			"icon": "lucide-sprout",
			"headline": headline,
			"fields": fields,
			"url": route("Lead", name),
		}
	]

	if ERP.source().has_doctype("Opportunity"):
		out.append(
			recent(
				"Opportunity",
				{"opportunity_from": "Lead", "party_name": name},
				["name", "status", "transaction_date", "opportunity_amount", "currency"],
				_("Opportunities"),
				lambda row: formatdate(row.transaction_date),
				lambda row: money(row.opportunity_amount, row.currency) if row.opportunity_amount else "",
				_("No opportunities yet"),
				f"/app/opportunity?party_name={name}",
			)
		)

	return out


def supplier_cards(name):
	doc = record("Supplier", name)
	fields = filled(
		[
			(_("GSTIN"), doc.get("gstin")),
			(_("Group"), doc.get("supplier_group")),
			(_("Country"), doc.get("country")),
		]
	)
	due = outstanding("Purchase Invoice", "supplier", name)
	if due:
		fields.append({"label": _("Payable"), "value": due})

	return [
		{
			"title": _("Supplier"),
			"icon": "lucide-truck",
			"headline": doc.get("supplier_name") or name,
			"badges": [badge for badge in [gst_badge(doc)] if badge],
			"fields": fields,
			"url": route("Supplier", name),
		},
		recent(
			"Purchase Order",
			{"supplier": name},
			["name", "status", "transaction_date", "grand_total", "currency"],
			_("Recent purchase orders"),
			lambda row: formatdate(row.transaction_date),
			lambda row: money(row.grand_total, row.currency),
			_("No purchase orders yet"),
			f"/app/purchase-order?supplier={name}",
		),
	]


def unlinked(contact):
	return not contact.reference_docname


def unlinked_or_lead(contact):
	return not contact.reference_docname or contact.reference_doctype == "Lead"


def create_lead(contact):
	source = ERP.source()
	lead = source.insert(
		{
			"doctype": "Lead",
			"first_name": contact.contact_name or contact.mobile_no,
			"mobile_no": frappe_phone(contact.mobile_no),
			"whatsapp_no": frappe_phone(contact.mobile_no),
			"email_id": contact.email,
			"source": "WhatsApp" if source.exists("Lead Source", "WhatsApp") else None,
		}
	)

	return "Lead", lead.name


def create_customer(contact, ignore_permissions=False):
	source = ERP.source()
	if contact.reference_doctype == "Lead" and contact.reference_docname:
		mapped = source.call(
			"erpnext.crm.doctype.lead.lead.make_customer", source_name=contact.reference_docname
		)
		customer = source.insert(mapped, ignore_permissions=ignore_permissions)

		return "Customer", customer.name

	customer = source.insert(
		{
			"doctype": "Customer",
			"customer_name": contact.contact_name or contact.mobile_no,
			"customer_type": "Individual",
			"mobile_no": frappe_phone(contact.mobile_no),
			"email_id": contact.email,
		},
		ignore_permissions=ignore_permissions,
	)

	return "Customer", customer.name


def since(before):
	return {"creation": ["<", before]} if before else {}


def totals(rows):
	rows = [row for row in rows if flt(row.get("total"))]
	return ", ".join(money(row.total, row.currency) for row in rows) if rows else None


def unbilled_orders(source, customers, fields):
	return [
		row
		for row in source.get_list(
			"Sales Order",
			filters={
				"customer": ["in", customers],
				"docstatus": 1,
				"per_billed": ["<", 100],
				"status": ["not in", ["Closed", "Cancelled"]],
			},
			fields=["customer", "per_billed", *fields],
			limit=0,
		)
		if flt(row.get("per_billed")) < 100
	]


def unbilled(row, field):
	return flt(row.get(field)) * (100 - flt(row.get("per_billed"))) / 100


def stats(doctype, name):
	source = ERP.source()
	if doctype == "Customer":
		invoices = source.get_list(
			"Sales Invoice",
			filters={"customer": name, "docstatus": 1},
			fields=[
				"sum(grand_total) as total",
				"sum(outstanding_amount) as due",
				"max(posting_date) as last",
				"currency",
			],
			group_by="currency",
			limit=10,
		)
		orders = source.get_list(
			"Sales Order",
			filters={"customer": name, "docstatus": 1},
			fields=["count(name) as count", "max(transaction_date) as last"],
			limit=1,
		)
		order = orders[0] if orders else {}
		last = max(
			[part for part in [order.get("last"), *[row.get("last") for row in invoices]] if part],
			default=None,
		)
		due = [{"total": row.get("due"), "currency": row.get("currency")} for row in invoices]
		value = {}
		for row in invoices:
			value[row.get("currency")] = value.get(row.get("currency"), 0) + flt(row.get("total"))
		for row in unbilled_orders(source, [name], ["grand_total", "currency"]):
			value[row.get("currency")] = value.get(row.get("currency"), 0) + unbilled(row, "grand_total")
		worth = [frappe._dict(total=total, currency=currency) for currency, total in value.items() if total]
		out = [
			{
				"key": "lifetime_value",
				"label": _("Lifetime value"),
				"value": totals(worth) or money(0),
				"hint": _("Invoiced, plus orders not billed yet"),
			},
			{"key": "orders", "label": _("Orders"), "value": int(order.get("count") or 0)},
			{
				"key": "last_purchase",
				"label": _("Last purchase"),
				"value": str(last) if last else None,
				"type": "date",
			},
		]
		outstanding = totals([frappe._dict(row) for row in due])
		if outstanding:
			out.append(
				{"key": "outstanding", "label": _("Outstanding"), "value": outstanding, "theme": "red"}
			)
		return out

	if doctype == "Lead":
		row = source.get_value("Lead", name, ["status", "source", "creation"]) or {}
		return [
			{"key": "lead_status", "label": _("Lead status"), "value": row.get("status")},
			{"key": "lead_source", "label": _("Source"), "value": row.get("source")},
			{
				"key": "lead_since",
				"label": _("Lead since"),
				"value": str(row.get("creation")) if row.get("creation") else None,
				"type": "date",
			},
		]

	if doctype == "Supplier":
		orders = source.get_list(
			"Purchase Order",
			filters={"supplier": name, "docstatus": 1},
			fields=["sum(grand_total) as total", "currency"],
			group_by="currency",
			limit=10,
		)
		return [{"key": "purchases", "label": _("Purchases"), "value": totals(orders) or money(0)}]

	return []


def event(doctype, row, title, subtitle=None, icon="lucide-file-text"):
	return {
		"id": f"{doctype}:{row.name}",
		"at": str(row.creation),
		"title": title,
		"subtitle": subtitle,
		"status": row.get("status"),
		"theme": theme(row.get("status")),
		"url": route(doctype, row.name),
		"icon": icon,
	}


def timeline(doctype, name, before=None, limit=30):
	source = ERP.source()
	out = []
	if doctype == "Customer":
		for row in source.get_list(
			"Sales Order",
			filters={"customer": name, "docstatus": ["!=", 2], **since(before)},
			fields=["name", "creation", "status", "grand_total", "currency"],
			order_by="creation desc",
			limit=limit,
		):
			out.append(
				event(
					"Sales Order",
					row,
					_("Order {0}").format(row.name),
					money(row.grand_total, row.currency),
					"lucide-package",
				)
			)
		for row in source.get_list(
			"Sales Invoice",
			filters={"customer": name, "docstatus": ["!=", 2], **since(before)},
			fields=["name", "creation", "status", "grand_total", "outstanding_amount", "currency"],
			order_by="creation desc",
			limit=limit,
		):
			due = flt(row.outstanding_amount)
			detail = money(row.grand_total, row.currency)
			if due:
				detail = _("{0} · {1} due").format(detail, money(due, row.currency))
			out.append(
				event("Sales Invoice", row, _("Invoice {0}").format(row.name), detail, "lucide-receipt")
			)
		for row in source.get_list(
			"Payment Entry",
			filters={"party_type": "Customer", "party": name, "docstatus": 1, **since(before)},
			fields=[
				"name",
				"creation",
				"status",
				"paid_amount",
				"paid_from_account_currency as currency",
				"mode_of_payment",
			],
			order_by="creation desc",
			limit=limit,
		):
			out.append(
				event(
					"Payment Entry",
					row,
					_("Payment received {0}").format(money(row.paid_amount, row.currency)),
					row.mode_of_payment,
					"lucide-wallet",
				)
			)
	elif doctype == "Lead":
		lead = source.get_value("Lead", name, ["name", "creation", "status", "source"])
		if lead and (not before or str(lead.creation) < before):
			out.append(
				event("Lead", frappe._dict(lead), _("Became a lead"), lead.get("source"), "lucide-sprout")
			)
		for row in source.get_list(
			"Quotation",
			filters={"quotation_to": "Lead", "party_name": name, "docstatus": ["!=", 2], **since(before)},
			fields=["name", "creation", "status", "grand_total", "currency"],
			order_by="creation desc",
			limit=limit,
		):
			out.append(
				event(
					"Quotation",
					row,
					_("Quotation {0}").format(row.name),
					money(row.grand_total, row.currency),
					"lucide-file-text",
				)
			)
	elif doctype == "Supplier":
		for row in source.get_list(
			"Purchase Order",
			filters={"supplier": name, "docstatus": ["!=", 2], **since(before)},
			fields=["name", "creation", "status", "grand_total", "currency"],
			order_by="creation desc",
			limit=limit,
		):
			out.append(
				event(
					"Purchase Order",
					row,
					_("Purchase order {0}").format(row.name),
					money(row.grand_total, row.currency),
					"lucide-truck",
				)
			)
	return out


def chunks(values, size=200):
	values = list(values)
	for start in range(0, len(values), size):
		yield values[start : start + size]


def metrics(doctype, names):
	if doctype != "Customer" or not names:
		return {}
	source = ERP.source()
	out = {}
	for batch in chunks(names):
		for row in source.get_list(
			"Sales Invoice",
			filters={"customer": ["in", batch], "docstatus": 1, "is_return": 0},
			fields=[
				"customer",
				"count(name) as orders",
				"sum(base_grand_total) as total",
				"sum(base_outstanding_amount) as due",
				"min(posting_date) as first",
				"max(posting_date) as last",
			],
			group_by="customer",
			limit=0,
		):
			out[row.get("customer")] = {
				"lifetime_value": flt(row.get("total")),
				"order_count": int(row.get("orders") or 0),
				"outstanding_amount": flt(row.get("due")),
				"first_purchase_on": row.get("first"),
				"last_purchase_on": row.get("last"),
			}
		try:
			spend = source.get_list(
				"Sales Invoice",
				filters={"customer": ["in", batch], "docstatus": 1, "is_return": 0},
				fields=[
					"customer",
					"`tabSales Invoice Item`.item_group as item_group",
					"sum(`tabSales Invoice Item`.base_net_amount) as total",
				],
				group_by="customer, `tabSales Invoice Item`.item_group",
				limit=0,
			)
		except Exception:
			frappe.log_error(title="OneChat favourite category")
			spend = []
		best = {}
		for row in spend:
			customer, total = row.get("customer"), flt(row.get("total"))
			if row.get("item_group") and total > best.get(customer, (None, 0))[1]:
				best[customer] = (row.get("item_group"), total)
		for customer, (group, _total) in best.items():
			out.setdefault(customer, {})["favourite_category"] = group
		try:
			orders = unbilled_orders(source, batch, ["base_grand_total", "transaction_date"])
		except Exception:
			frappe.log_error(title="OneChat unbilled orders")
			orders = []
		for row in orders:
			entry = out.setdefault(
				row.get("customer"), {"lifetime_value": 0, "order_count": 0, "outstanding_amount": 0}
			)
			entry["lifetime_value"] = flt(entry.get("lifetime_value")) + unbilled(row, "base_grand_total")
			if not flt(row.get("per_billed")):
				entry["order_count"] = int(entry.get("order_count") or 0) + 1
			day = row.get("transaction_date")
			if day:
				first, last = entry.get("first_purchase_on"), entry.get("last_purchase_on")
				entry["first_purchase_on"] = min([part for part in [first, day] if part], key=str)
				entry["last_purchase_on"] = max([part for part in [last, day] if part], key=str)
	return out
