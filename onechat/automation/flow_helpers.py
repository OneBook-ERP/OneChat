import re
from typing import Any

import frappe

from onechat.api_types import JSON
from onechat.workspace.session import require_admin


@frappe.whitelist()
def get_doctype_list():
	require_admin()
	doctypes = frappe.get_list(
		"DocType",
		filters={"istable": 0, "issingle": 0, "is_virtual": 0},
		fields=["name", "module", "description"],
		order_by="name",
	)
	return doctypes


@frappe.whitelist()
def get_doctype_fields(doctype: str):
	require_admin()
	if not doctype:
		return []

	from onechat.integrations.records import fields

	return fields(doctype)


@frappe.whitelist()
def get_whatsapp_templates():
	require_admin()
	templates = frappe.get_list(
		"WhatsApp Templates",
		fields=["name", "template_name", "language", "category", "status"],
		filters={"status": "Approved"},
		order_by="name",
	)
	return templates


@frappe.whitelist()
def get_template_details(template_name: str):
	require_admin()
	if not template_name:
		return None

	template = frappe.get_doc("WhatsApp Templates", template_name)

	variables = []
	if template.body:
		matches = re.findall(r"\{\{(\d+)\}\}", template.body)
		variables = [{"index": m, "name": f"Variable {m}"} for m in sorted(set(matches))]

	buttons = []
	if hasattr(template, "buttons") and template.buttons:
		for idx, btn in enumerate(template.buttons):
			if btn.type == "URL" and "{{" in btn.url:
				buttons.append({"index": idx, "name": btn.text})

	return {
		"name": template.name,
		"template_name": template.template_name,
		"body": template.body,
		"language": template.language,
		"category": template.category,
		"variables": variables,
		"buttons": buttons,
		"header": template.header if hasattr(template, "header") else None,
		"footer": template.footer if hasattr(template, "footer") else None,
	}


@frappe.whitelist()
def get_doc_events():
	require_admin()
	return [
		{"value": "before_insert", "label": "Before Insert"},
		{"value": "after_insert", "label": "After Insert"},
		{"value": "before_validate", "label": "Before Validate"},
		{"value": "validate", "label": "Validate"},
		{"value": "on_update", "label": "On Update"},
		{"value": "before_submit", "label": "Before Submit"},
		{"value": "on_submit", "label": "On Submit"},
		{"value": "before_cancel", "label": "Before Cancel"},
		{"value": "on_cancel", "label": "On Cancel"},
		{"value": "on_trash", "label": "On Trash"},
		{"value": "after_delete", "label": "After Delete"},
		{"value": "before_update_after_submit", "label": "Before Update After Submit"},
		{"value": "on_update_after_submit", "label": "On Update After Submit"},
	]


@frappe.whitelist()
def validate_expression(expression: str, sample_context: JSON = None):
	require_admin()
	if not expression:
		return {"valid": False, "error": "Expression is empty"}

	try:
		if expression.startswith("doc."):
			field = expression[4:]
			if not field:
				return {"valid": False, "error": "Field name is required after 'doc.'"}
			return {"valid": True, "type": "doc_field"}

		elif expression.startswith("context."):
			path = expression[8:]
			if not path:
				return {"valid": False, "error": "Path is required after 'context.'"}
			return {"valid": True, "type": "context_path"}

		elif expression in ["doctype", "docname", "trigger"]:
			return {"valid": True, "type": "context_variable"}

		else:
			return {"valid": True, "type": "literal"}

	except Exception as e:
		return {"valid": False, "error": str(e)}


@frappe.whitelist()
def get_context_fields(trigger_type: str, doctype: str | None = None):
	require_admin()
	fields = {
		"common": [
			{"path": "doctype", "label": "Document Type", "type": "string"},
			{"path": "docname", "label": "Document Name", "type": "string"},
			{"path": "trigger", "label": "Trigger Type", "type": "string"},
		]
	}

	if trigger_type == "ERPNext Document Event" and doctype:
		doc_fields = get_doctype_fields(doctype)
		fields["doc"] = [
			{"path": f"doc.{f['fieldname']}", "label": f["label"], "type": f["fieldtype"]} for f in doc_fields
		]

	elif trigger_type == "WhatsApp Incoming":
		fields["whatsapp"] = [
			{"path": "whatsapp.from", "label": "From Number", "type": "string"},
			{"path": "whatsapp.message", "label": "Message Text", "type": "string"},
			{"path": "whatsapp.message_id", "label": "Message ID", "type": "string"},
		]

	return fields
