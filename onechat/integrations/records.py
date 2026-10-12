import frappe
from frappe import _
from frappe.utils import cint

from onechat.api_types import JSON
from onechat.integrations import connection
from onechat.workspace.session import require_app_user

HIDDEN_TYPES = ("Section Break", "Column Break", "Tab Break", "HTML")


@frappe.whitelist()
def search(doctype: str, txt: str = "", filters: JSON = None, page_length: int | str = 20):
	require_app_user()
	filters = frappe.parse_json(filters) if filters else None
	page_length = min(cint(page_length) or 20, 50)

	sites = connection.remote_sites() if doctype == "DocType" else []
	if sites:
		rows = local_search(doctype, txt, filters, page_length)
		seen = {row.get("value") for row in rows}
		query = (txt or "").lower()
		for site in sites:
			try:
				names = connection.remote_doctypes(site)
			except connection.RemoteError:
				continue
			for name in names:
				if query in name.lower() and name not in seen and not connection.local_doctype(name):
					seen.add(name)
					rows.append({"value": name, "description": _("On your {0} site").format(site.label)})
		return rows[: page_length * 2]

	source = connection.source_for(doctype)
	if source.remote:
		return source.search(doctype, txt, filters, page_length)

	return local_search(doctype, txt, filters, page_length)


def local_search(doctype, txt, filters, page_length):
	from frappe.desk.search import search_link

	return search_link(doctype, txt or "", filters=filters, page_length=page_length) or []


def fields(doctype):
	source = connection.source_for(doctype)
	if source.remote:
		return [row for row in source.meta_fields(doctype) if row["fieldtype"] not in HIDDEN_TYPES]

	return [
		{
			"fieldname": df.fieldname,
			"label": df.label or df.fieldname,
			"fieldtype": df.fieldtype,
			"options": df.options,
			"reqd": df.reqd,
		}
		for df in frappe.get_meta(doctype).fields
		if df.fieldtype not in HIDDEN_TYPES
	]
