import frappe
from frappe import _
from frappe.utils import cint, strip_html

from onechat.workspace.session import can_use_app, is_admin

SNIPPET = 120


@frappe.whitelist()
def search(query: str, limit: int | str = 5):
	if not can_use_app():
		frappe.throw(_("You do not have access to OneChat"), frappe.PermissionError)

	text = (query or "").strip()
	result = {"contacts": [], "messages": [], "notes": [], "templates": [], "quick_replies": []}
	if len(text) < 2:
		return result

	limit = min(max(cint(limit), 1), 20)
	like = f"%{text}%"

	from onechat.workspace.session import can_read

	if can_read("OneChat Contact"):
		result["contacts"] = contacts(like, limit)
	if can_read("OneChat Message"):
		result["messages"] = messages(text, like, limit)
	if can_read("OneChat Note"):
		result["notes"] = notes(text, like, limit)
	if is_admin() and can_read("WhatsApp Templates"):
		result["templates"] = templates(like, limit)
	if frappe.db.exists("DocType", "OneChat Quick Reply"):
		result["quick_replies"] = quick_replies(like, limit)

	return result


def contacts(like, limit):
	rows = frappe.get_list(
		"OneChat Contact",
		or_filters={"contact_name": ["like", like], "mobile_no": ["like", like], "email": ["like", like]},
		fields=["name", "contact_name", "mobile_no", "email"],
		order_by="modified desc",
		limit_page_length=limit,
	)

	return [
		{
			"name": row.name,
			"title": row.contact_name or row.mobile_no or row.name,
			"subtitle": " · ".join(value for value in (row.mobile_no, row.email) if value),
		}
		for row in rows
	]


def messages(text, like, limit):
	rows = frappe.get_list(
		"OneChat Message",
		filters={
			"message": ["like", like],
			"content_type": "text",
			"message_type": ["!=", "Template"],
			"whatsapp_contact": ["is", "set"],
		},
		fields=["name", "message", "whatsapp_contact", "creation", "type"],
		order_by="creation desc",
		limit_page_length=limit,
	)
	names = {row.whatsapp_contact for row in rows}
	labels = {}
	if names:
		labels = {
			row.name: row.contact_name or row.mobile_no or row.name
			for row in frappe.get_all(
				"OneChat Contact",
				filters={"name": ["in", list(names)]},
				fields=["name", "contact_name", "mobile_no"],
			)
		}

	return [
		{
			"name": row.name,
			"snippet": snippet(row.message, text),
			"whatsapp_contact": row.whatsapp_contact,
			"contact_name": labels.get(row.whatsapp_contact, row.whatsapp_contact),
			"type": row.type,
			"creation": row.creation,
		}
		for row in rows
	]


def notes(text, like, limit):
	rows = frappe.get_list(
		"OneChat Note",
		or_filters={"title": ["like", like], "content": ["like", like]},
		fields=["name", "title", "content", "reference_doctype", "reference_docname"],
		order_by="modified desc",
		limit_page_length=limit,
	)

	return [
		{
			"name": row.name,
			"title": row.title or _("Untitled note"),
			"snippet": snippet(strip_html(row.content or ""), text),
			"reference_doctype": row.reference_doctype,
			"reference_docname": row.reference_docname,
		}
		for row in rows
	]


def templates(like, limit):
	rows = frappe.get_list(
		"WhatsApp Templates",
		or_filters={"template_name": ["like", like], "actual_name": ["like", like]},
		fields=["name", "template_name", "actual_name", "status"],
		order_by="modified desc",
		limit_page_length=limit,
	)

	return [
		{
			"name": row.name,
			"title": row.template_name or row.name,
			"subtitle": row.actual_name,
			"status": row.status,
		}
		for row in rows
	]


def quick_replies(like, limit):
	meta = frappe.get_meta("OneChat Quick Reply")
	fields = [field for field in ("shortcut", "title", "message") if meta.has_field(field)]
	searchable = [field for field in ("shortcut", "title") if field in fields]
	if not searchable:
		return []

	rows = frappe.get_list(
		"OneChat Quick Reply",
		or_filters={field: ["like", like] for field in searchable},
		fields=["name", *fields],
		order_by="modified desc",
		limit_page_length=limit,
	)

	return [
		{
			"name": row.name,
			"title": row.get("title") or row.get("shortcut") or row.name,
			"shortcut": row.get("shortcut"),
			"snippet": (row.get("message") or "")[:SNIPPET],
		}
		for row in rows
	]


def snippet(value, text):
	value = " ".join((value or "").split())
	if len(value) <= SNIPPET:
		return value

	index = value.lower().find(text.lower())
	start = max(0, index - SNIPPET // 3) if index > -1 else 0
	end = min(len(value), start + SNIPPET)
	out = value[start:end]

	return ("…" if start else "") + out + ("…" if end < len(value) else "")
