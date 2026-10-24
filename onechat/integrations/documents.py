import frappe
from frappe import _

from onechat.integrations import connection

SOURCES = {
	"customer": {
		"site": "erpnext",
		"doctype": "Customer",
		"party": "name",
		"parties": ("Customer",),
		"extra": ("customer_name", "disabled"),
	},
	"lead": {
		"site": "erpnext",
		"doctype": "Lead",
		"party": "name",
		"parties": ("Lead",),
		"extra": ("lead_name", "lead_owner", "qualification_status"),
	},
	"sales_order": {
		"site": "erpnext",
		"doctype": "Sales Order",
		"party": "customer",
		"parties": ("Customer",),
		"extra": ("delivery_date", "advance_paid", "per_delivered", "per_billed"),
	},
	"sales_invoice": {
		"site": "erpnext",
		"doctype": "Sales Invoice",
		"party": "customer",
		"parties": ("Customer",),
		"extra": ("outstanding_amount", "is_return"),
	},
	"delivery_note": {
		"site": "erpnext",
		"doctype": "Delivery Note",
		"party": "customer",
		"parties": ("Customer",),
		"extra": ("is_return",),
	},
	"payment_entry": {
		"site": "erpnext",
		"doctype": "Payment Entry",
		"party": "party",
		"party_type": "party_type",
		"parties": ("Customer",),
		"extra": ("paid_amount", "mode_of_payment", "unallocated_amount"),
	},
	"quotation": {
		"site": "erpnext",
		"doctype": "Quotation",
		"party": "party_name",
		"party_type": "quotation_to",
		"parties": ("Customer", "Lead"),
		"extra": ("valid_till", "order_type"),
	},
	"crm_deal": {
		"site": "crm",
		"doctype": "CRM Deal",
		"party": "name",
		"parties": ("CRM Deal",),
		"extra": (
			"deal_owner",
			"source",
			"deal_value",
			"expected_deal_value",
			"expected_closure_date",
			"closed_date",
			"probability",
			"annual_revenue",
			"territory",
			"industry",
		),
	},
	"crm_lead": {
		"site": "crm",
		"doctype": "CRM Lead",
		"party": "name",
		"parties": ("CRM Lead",),
		"extra": ("lead_owner", "source", "industry", "territory", "annual_revenue", "converted"),
	},
}
EXCLUDE = {
	"default_currency",
	"set_target_warehouse",
	"paid_from",
	"paid_to",
	"reference_no",
	"party_type",
	"quotation_to",
}
TYPES = {
	"Int": "number",
	"Float": "number",
	"Currency": "number",
	"Percent": "number",
	"Date": "date",
	"Datetime": "date",
	"Select": "choice",
	"Check": "flag",
	"Data": "text",
	"Link": "text",
	"Dynamic Link": "text",
	"Phone": "text",
	"Small Text": "text",
	"Text": "text",
	"Long Text": "text",
}
SKIP = {"naming_series", "amended_from"}


def memo():
	cache = getattr(frappe.local, "onechat_documents", None)
	if cache is None:
		cache = frappe.local.onechat_documents = {}
	return cache


def site(key):
	return connection.site(SOURCES[key]["site"])


def available():
	cache = memo()
	if "available" not in cache:
		out = []
		for key, spec in SOURCES.items():
			try:
				row = site(key)
				if row.ready() and row.source().has_doctype(spec["doctype"]):
					out.append(key)
			except Exception:
				frappe.log_error(title=f"OneChat segment documents: {spec['doctype']}")
		cache["available"] = out
	return list(cache["available"])


def fields(key):
	doctype = SOURCES[key]["doctype"]
	row = site(key)
	if row.is_remote():
		rows = row.source().meta_fields(doctype)
	else:
		rows = [
			{
				"fieldname": df.fieldname,
				"label": df.label,
				"fieldtype": df.fieldtype,
				"options": df.options,
				"hidden": df.hidden,
				"in_standard_filter": df.in_standard_filter,
				"in_list_view": df.in_list_view,
			}
			for df in frappe.get_meta(doctype).fields
			if not df.permlevel
		]

	out = []
	for df in rows:
		kind = TYPES.get(df.get("fieldtype"))
		if not kind or df.get("fieldname") in SKIP or df.get("hidden"):
			continue
		if not useful(df, SOURCES[key]):
			continue
		entry = {
			"fieldname": df["fieldname"],
			"label": df.get("label") or df["fieldname"],
			"type": kind,
			"date_only": df.get("fieldtype") == "Date",
		}
		if kind == "choice":
			entry["options"] = [
				{"value": option, "label": _(option)}
				for option in (df.get("options") or "").split("\n")
				if option.strip()
			]
		out.append(entry)
	return out


def useful(df, spec):
	# What the doctype's own list view filters and shows, plus the amounts and dates people segment by.
	fieldname = df.get("fieldname")
	if fieldname in EXCLUDE:
		return False
	if fieldname == "status" or fieldname in spec.get("extra", ()):
		return True
	return bool(df.get("in_standard_filter") or df.get("in_list_view"))


def catalog():
	cache = memo()
	if "catalog" not in cache:
		out = {}
		for key in available():
			spec = SOURCES[key]
			try:
				rows = fields(key)
			except Exception:
				frappe.log_error(title=f"OneChat segment fields: {spec['doctype']}")
				continue
			for row in rows:
				out[f"{key}.{row['fieldname']}"] = {**row, "group": spec["doctype"], "document": key}
		cache["catalog"] = out
	return cache["catalog"]


def parties_with(key, party_type, condition, filters):
	spec = SOURCES[key]
	row = site(key)
	if not row.is_remote():
		table = frappe.qb.DocType(spec["doctype"])
		where = condition(table)
		if spec.get("party_type"):
			where = where & (table[spec["party_type"]] == party_type)
		return frappe.qb.from_(table).select(table[spec["party"]]).where(where).distinct()

	query = [list(item) for item in filters]
	if spec.get("party_type"):
		query.append([spec["party_type"], "=", party_type])
	rows = row.source().get_list(
		spec["doctype"], filters=query, fields=[spec["party"]], group_by=spec["party"], limit=0
	)
	return sorted({item.get(spec["party"]) for item in rows if item.get(spec["party"])})
