import json
import re

import frappe
from frappe import _
from frappe.utils import cint

from onechat.assistant.tools import Tool, ToolError
from onechat.integrations import connection

LIST_LIMIT = 20
MAX_LIMIT = 50
CHILD_ROWS = 20
FIELD_LIMIT = 8
IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]*$")
ORDER = re.compile(r"^[a-z][a-z0-9_]*( asc| desc)?$", re.I)
BLOCKED = frozenset(
	{
		"Access Log",
		"Activity Log",
		"Client Script",
		"Custom DocPerm",
		"Custom Field",
		"Deleted Document",
		"DocField",
		"DocPerm",
		"DocType",
		"Error Log",
		"Has Role",
		"Module Def",
		"OAuth Authorization Code",
		"OAuth Bearer Token",
		"OAuth Client",
		"OneChat Agent Token",
		"OneChat Connection",
		"OneChat Message",
		"OneChat Settings",
		"Property Setter",
		"Role",
		"Role Profile",
		"Scheduled Job Type",
		"Server Script",
		"System Settings",
		"User",
		"User Permission",
		"Version",
		"Webhook",
		"WhatsApp Message",
	}
)
PROTECTED = frozenset({"name", "doctype", "owner", "creation", "modified", "modified_by", "docstatus", "idx"})
CHILD_INTERNAL = PROTECTED | {"parent", "parentfield", "parenttype"}
NO_VALUE = (
	"Section Break",
	"Column Break",
	"Tab Break",
	"HTML",
	"Button",
	"Table",
	"Table MultiSelect",
	"Heading",
)
FILTERS_HELP = (
	'Filters as {"field": value} or {"field": ["operator", value]}, for example '
	'{"status": "Unpaid", "posting_date": [">=", "2026-01-01"]}.'
)


def required(call, key):
	value = call.get(key)
	if not value:
		raise ToolError(_("Say which {0}.").format(key.replace("_", " ")))
	return value


def mapping(value, label):
	if isinstance(value, str):
		try:
			value = json.loads(value)
		except ValueError as error:
			raise ToolError(_("{0} must be JSON.").format(label)) from error
	if value in (None, "", [], {}):
		return {}
	if not isinstance(value, dict | list):
		raise ToolError(_("{0} must be an object.").format(label))
	return value


def checked_doctype(call, write=False):
	doctype = str(required(call, "doctype")).strip()
	if doctype in BLOCKED:
		raise ToolError(_("The assistant can't use {0} records.").format(doctype))
	source = connection.source_for(doctype)
	if source.remote:
		return doctype, source
	if not frappe.db.exists("DocType", doctype):
		raise ToolError(_("There is no DocType called {0}.").format(doctype))
	meta = frappe.get_meta(doctype)
	if write and (meta.issingle or meta.istable):
		raise ToolError(_("The assistant can't create or change {0} records.").format(doctype))
	return doctype, source


def default_fields(source, doctype):
	if source.remote:
		rows = source.meta_fields(doctype)
		title = None
	else:
		meta = frappe.get_meta(doctype)
		rows = [field.as_dict() for field in meta.fields]
		title = meta.title_field
	listed = [
		row["fieldname"]
		for row in rows
		if row.get("in_list_view") and row.get("fieldtype") not in NO_VALUE and row.get("fieldname")
	]
	out = ["name", *([title] if title else []), *listed[:FIELD_LIMIT]]
	return list(dict.fromkeys(out))


def text_filters(source, doctype, text):
	if not text:
		return None
	like = f"%{text}%"
	fields = ["name"]
	if not source.remote:
		meta = frappe.get_meta(doctype)
		fields += [meta.title_field] if meta.title_field else []
		fields += [field.strip() for field in (meta.search_fields or "").split(",") if field.strip()]
	return [[field, "like", like] for field in dict.fromkeys(fields)]


def field_list(call, source, doctype):
	fields = call.get("fields") or default_fields(source, doctype)
	if not isinstance(fields, list) or not all(isinstance(f, str) and IDENTIFIER.match(f) for f in fields):
		raise ToolError(_("fields must be a list of field names."))
	return fields


def search_records(call):
	doctype, source = checked_doctype(call)
	order_by = call.get("order_by") or "modified desc"
	if not ORDER.match(order_by):
		raise ToolError(_("order_by must look like 'modified desc'."))
	rows = source.get_list(
		doctype,
		fields=field_list(call, source, doctype),
		filters=mapping(call.get("filters"), "filters") or None,
		or_filters=text_filters(source, doctype, call.get("text")),
		order_by=order_by,
		limit=min(cint(call.get("limit")) or LIST_LIMIT, MAX_LIMIT),
	)
	return {"doctype": doctype, "count": len(rows), "rows": rows}


def compact_row(row):
	return {key: value for key, value in row.items() if key not in CHILD_INTERNAL and value not in (None, "")}


def compact(doc):
	out = {}
	for key, value in doc.items():
		if key.startswith("_") or value in (None, "", []):
			continue
		if isinstance(value, list):
			out[key] = [compact_row(row) for row in value[:CHILD_ROWS] if isinstance(row, dict)]
			if len(value) > CHILD_ROWS:
				out[f"{key}_more_rows"] = len(value) - CHILD_ROWS
			continue
		out[key] = value
	return out


def get_record(call):
	doctype, source = checked_doctype(call)
	name = required(call, "name")
	if not source.remote and not frappe.has_permission(doctype, "read", name):
		raise frappe.PermissionError(_("You can't read {0} {1}.").format(doctype, name))
	return compact(source.get_doc(doctype, name))


def checked_field(value):
	if value and not IDENTIFIER.match(value):
		raise ToolError(_("{0} is not a field name.").format(value))
	return value


def count_and_total(call):
	doctype, source = checked_doctype(call)
	total = checked_field(call.get("sum_field"))
	group = checked_field(call.get("group_by"))
	filters = mapping(call.get("filters"), "filters") or None
	if group:
		fields = [group, "count(name) as count", *([f"sum({total}) as total"] if total else [])]
		rows = source.get_list(
			doctype, fields=fields, filters=filters, group_by=group, order_by=f"{group} asc", limit=MAX_LIMIT
		)
		return {"doctype": doctype, "groups": rows}
	count = source.get_list(doctype, fields=["count(name) as count"], filters=filters, limit=1)
	out = {"doctype": doctype, "count": (count[0] if count else {}).get("count", 0)}
	if total:
		summed = source.get_list(doctype, fields=[f"sum({total}) as total"], filters=filters, limit=1)
		out["total"] = (summed[0] if summed else {}).get("total") or 0
	return out


def clean_values(values):
	if not isinstance(values, dict):
		raise ToolError(_("values must be an object of field: value pairs."))
	out = {}
	for key, value in values.items():
		if key in PROTECTED:
			continue
		if isinstance(value, list):
			value = [
				{k: v for k, v in row.items() if k not in CHILD_INTERNAL}
				for row in value
				if isinstance(row, dict)
			]
		out[key] = value
	return out


def values_of(call):
	return clean_values(mapping(call.get("values") or call.get("data"), "values"))


def create_document(call):
	doctype, source = checked_doctype(call, write=True)
	doc = source.insert({**values_of(call), "doctype": doctype})
	return {"created": doctype, "name": doc.get("name")}


def update_document(call):
	doctype, source = checked_doctype(call, write=True)
	name = required(call, "name")
	values = values_of(call)
	if not values:
		raise ToolError(_("Say which fields to change."))
	source.update(doctype, name, values)
	return {"updated": doctype, "name": name, "fields": sorted(values)}


def submit_document(call):
	doctype, source = checked_doctype(call, write=True)
	name = required(call, "name")
	if source.remote:
		source.submit(source.get_doc(doctype, name))
	else:
		frappe.get_doc(doctype, name).submit()
	return {"submitted": doctype, "name": name}


def schema(properties, required_keys=()):
	return {"type": "object", "properties": properties, "required": list(required_keys)}


DOCTYPE = {"type": "string", "description": "Exact DocType name, for example Sales Order or CRM Lead."}
NAME = {"type": "string", "description": "Exact record name (ID)."}
FILTERS = {"type": "object", "description": FILTERS_HELP}
VALUES = {
	"type": "object",
	"description": "Field values as {fieldname: value}. Child tables are lists of row objects, "
	'for example {"items": [{"item_code": "CHAIR", "qty": 2}]}.',
}

TOOLS = [
	Tool(
		name="search_records",
		description="List records of any DocType the user can read, with filters, a text search on the name and \
title, and sorting. Use it to find records before opening or changing them.",
		schema=schema(
			{
				"doctype": DOCTYPE,
				"filters": FILTERS,
				"text": {"type": "string", "description": "Words to look for in the name or title."},
				"fields": {"type": "array", "items": {"type": "string"}, "description": "Fields to return."},
				"order_by": {"type": "string", "description": "For example 'posting_date desc'."},
				"limit": {"type": "integer", "description": f"At most {MAX_LIMIT}. Default {LIST_LIMIT}."},
			},
			["doctype"],
		),
		handler=search_records,
	),
	Tool(
		name="get_record",
		description="Open one record with all its fields and child table rows.",
		schema=schema({"doctype": DOCTYPE, "name": NAME}, ["doctype", "name"]),
		handler=get_record,
	),
	Tool(
		name="count_and_total",
		description="Count records and optionally add up one number field, overall or grouped by a field. \
Use it for totals and comparisons instead of listing many records.",
		schema=schema(
			{
				"doctype": DOCTYPE,
				"filters": FILTERS,
				"sum_field": {
					"type": "string",
					"description": "Number field to add up, for example grand_total.",
				},
				"group_by": {
					"type": "string",
					"description": "Field to group by, for example customer or status.",
				},
			},
			["doctype"],
		),
		handler=count_and_total,
	),
	Tool(
		name="create_document",
		description="Create a record. The user confirms before it is saved. Look up exact link values \
(customer, item codes) first instead of guessing them.",
		schema=schema({"doctype": DOCTYPE, "values": VALUES}, ["doctype", "values"]),
		handler=create_document,
		right="create",
	),
	Tool(
		name="update_document",
		description="Change fields on an existing record. The user confirms before it is saved.",
		schema=schema({"doctype": DOCTYPE, "name": NAME, "values": VALUES}, ["doctype", "name", "values"]),
		handler=update_document,
		right="write",
	),
	Tool(
		name="submit_document",
		description="Submit a draft record such as a Quotation, Sales Order or Sales Invoice. The user confirms \
first. A submitted record can only be reversed by cancelling it.",
		schema=schema({"doctype": DOCTYPE, "name": NAME}, ["doctype", "name"]),
		handler=submit_document,
		right="write",
	),
]
