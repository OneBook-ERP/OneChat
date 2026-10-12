import frappe
from frappe import _
from frappe.query_builder import Order
from frappe.query_builder.functions import Count
from frappe.utils import add_days, cint, getdate
from pypika.terms import Field

from onechat.api_types import JSON
from onechat.workspace.session import is_admin


def ensure_admin():
	if not is_admin():
		frappe.throw(_("Only OneChat admins can manage forms"), frappe.PermissionError)


MESSAGE = "OneChat Message"
FLOW = "WhatsApp Flow"
EXPORT_LIMIT = 10000


def response_query(names, from_date=None, to_date=None, search=None):
	incoming = frappe.qb.DocType(MESSAGE)
	query = frappe.qb.from_(incoming).where(
		(incoming.type == "Incoming") & (incoming.content_type == "flow") & incoming.flow.isin(names)
	)
	if from_date:
		query = query.where(incoming.creation >= getdate(from_date))
	if to_date:
		query = query.where(incoming.creation < add_days(getdate(to_date), 1))
	if search and search.strip():
		pattern = f"%{search.strip()}%"
		query = query.where(
			Field("from", table=incoming).like(pattern)
			| incoming.profile_name.like(pattern)
			| incoming.flow_response.like(pattern)
		)

	return query, incoming, incoming.flow


def narrowed(from_date=None, to_date=None, search=None):
	return bool(from_date or to_date or (search and search.strip()))


def count_responses(name, **filters):
	query, incoming = response_query([name], **filters)[:2]
	return cint(query.select(Count(incoming.name).as_("total")).run(as_dict=True)[0].total)


def resolve_form(response, reply_to=None):
	token = response.get("flow_token")
	if token and token != "unused":
		flow = frappe.db.get_value(MESSAGE, {"flow_token": token, "flow": ["is", "set"]}, "flow")
		if flow:
			return flow

	sent = (
		frappe.db.get_value(MESSAGE, {"message_id": reply_to}, ["flow", "template"], as_dict=True)
		if reply_to
		else None
	)
	if sent and sent.flow:
		return sent.flow
	if sent and sent.template:
		flow = template_form(sent.template)
		if flow:
			return flow

	return form_by_fields(response)


def template_form(template):
	buttons = frappe.get_all(
		"WhatsApp Button",
		filters={"parent": template, "parenttype": "WhatsApp Templates"},
		fields=["whatsapp_flow", "flow_id"],
	)
	for button in buttons:
		if button.whatsapp_flow:
			return button.whatsapp_flow
		if button.flow_id:
			flow = frappe.db.get_value(FLOW, {"flow_id": button.flow_id})
			if flow:
				return flow

	return None


def form_by_fields(response):
	keys = {key for key in response if key != "flow_token"}
	if not keys:
		return None

	found = {}
	for row in frappe.get_all(
		"WhatsApp Flow Field",
		filters={"parenttype": FLOW, "field_name": ["in", list(keys)]},
		fields=["parent", "field_name"],
	):
		found.setdefault(row.parent, set()).add(row.field_name)

	matches = [name for name, fields in found.items() if fields == keys]
	return matches[0] if len(matches) == 1 else None


def parse_response(value):
	data = frappe.parse_json(value) if value else {}
	if not isinstance(data, dict):
		return {}

	return {key: item for key, item in data.items() if key != "flow_token"}


@frappe.whitelist()
def response_counts(names: JSON = None):
	ensure_admin()
	from onechat.workspace.session import require_read

	require_read("WhatsApp Flow")
	names = frappe.parse_json(names) or []
	if not names:
		return {}

	query, incoming, form = response_query(names)
	rows = query.select(form.as_("form"), Count(incoming.name).as_("count")).groupby(form).run(as_dict=True)

	return {row.form: cint(row.count) for row in rows if row.form}


def response_rows(name, start=0, limit=20, **filters):
	query, incoming = response_query([name], **filters)[:2]
	rows = (
		query.select(
			incoming.name,
			Field("from", table=incoming).as_("phone"),
			incoming.profile_name,
			incoming.whatsapp_contact,
			incoming.creation,
			incoming.flow_response,
		)
		.orderby(incoming.creation, order=Order.desc)
		.limit(limit)
		.offset(start)
		.run(as_dict=True)
	)

	contacts = {row.whatsapp_contact for row in rows if row.whatsapp_contact}
	names = {}
	if contacts:
		names = {
			contact.name: contact.contact_name
			for contact in frappe.get_all(
				"OneChat Contact",
				filters={"name": ["in", list(contacts)]},
				fields=["name", "contact_name"],
			)
		}

	return [
		{
			"name": row.name,
			"phone": row.phone,
			"contact": row.whatsapp_contact,
			"contact_name": names.get(row.whatsapp_contact) or row.profile_name or "",
			"creation": row.creation,
			"response": parse_response(row.flow_response),
		}
		for row in rows
	]


@frappe.whitelist()
def responses(
	name: str,
	start: int | str = 0,
	limit: int | str = 20,
	from_date: str | None = None,
	to_date: str | None = None,
	search: str | None = None,
):
	ensure_admin()
	from onechat.workspace.session import require_read

	require_read("WhatsApp Flow")
	filters = {"from_date": from_date, "to_date": to_date, "search": search}
	total = count_responses(name, **filters)

	return {
		"rows": response_rows(name, max(cint(start), 0), min(cint(limit) or 20, 100), **filters),
		"total": total,
		"overall": count_responses(name) if narrowed(**filters) else total,
	}


@frappe.whitelist()
def export_responses(
	name: str, from_date: str | None = None, to_date: str | None = None, search: str | None = None
):
	ensure_admin()
	return response_rows(name, 0, EXPORT_LIMIT, from_date=from_date, to_date=to_date, search=search)
