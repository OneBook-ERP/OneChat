import json
import time
from typing import Any

import frappe
import requests
from frappe.model.workflow import apply_workflow


def resolve_expression(expr: str, context: dict[str, Any]) -> Any:
	if not expr:
		return None

	if expr.startswith("context."):
		path = expr[8:]
		parts = path.split(".")

		value = context
		for part in parts:
			if isinstance(value, dict):
				value = value.get(part)
			else:
				return None

		return value

	if expr.startswith("doc."):
		field = expr[4:]
		return context.get("doc", {}).get(field)

	if expr in ["doctype", "docname", "trigger"]:
		return context.get(expr)

	return expr


def exec_doc_event_trigger(node: dict, context: dict) -> dict:
	return context


def exec_whatsapp_incoming_trigger(node: dict, context: dict) -> dict:
	return context


def exec_scheduled_trigger(node: dict, context: dict) -> dict:
	return context


def exec_manual_trigger(node: dict, context: dict) -> dict:
	return context


def exec_send_whatsapp(node: dict, context: dict) -> dict:
	data = node.get("data", {})

	if "config" in data:
		config = data["config"]
	else:
		config = data

	to_expr = config.get("to")
	to = resolve_expression(to_expr, context)

	if not to:
		raise Exception(f"Recipient phone number not specified. Expression: '{to_expr}'")

	template_name = config.get("template_name")
	if not template_name:
		raise Exception("Template name not specified")

	from onechat.whatsapp.message import send_template_message

	message_id = send_template_message(
		reference_doctype=context.get("doctype", "Automation Flow"),
		reference_name=context.get("docname", ""),
		template=template_name,
		to=to,
	)

	print(f"[WhatsApp] Sent message {message_id} to {to} using template {template_name}")

	if "whatsapp" not in context:
		context["whatsapp"] = {}

	context["whatsapp"]["last_message_id"] = message_id
	context["whatsapp"]["last_sent_to"] = to
	context["whatsapp"]["last_template"] = template_name

	context["last_output"] = {"message_id": message_id, "to": to, "template": template_name}

	return context


def exec_send_email(node: dict, context: dict) -> dict:
	data = node.get("data", {})
	config = data.get("config", {}) if "config" in data else data

	to = resolve_expression(config.get("to"), context)
	subject = resolve_expression(config.get("subject"), context)
	message = resolve_expression(config.get("message"), context)
	cc = resolve_expression(config.get("cc"), context)
	bcc = resolve_expression(config.get("bcc"), context)

	if not to:
		raise Exception("Email recipient not specified")
	if not subject:
		raise Exception("Email subject not specified")

	frappe.sendmail(
		recipients=[to] if isinstance(to, str) else to,
		subject=subject,
		message=message,
		cc=cc.split(",") if cc and isinstance(cc, str) else cc,
		bcc=bcc.split(",") if bcc and isinstance(bcc, str) else bcc,
	)

	context["last_output"] = {"email_sent": to, "subject": subject}

	return context


def exec_create_document(node: dict, context: dict) -> dict:
	data = node.get("data", {})
	config = data.get("config", {}) if "config" in data else data

	doctype = config.get("doctype")
	if not doctype:
		raise Exception("DocType not specified")

	fields = config.get("fields", {})

	doc_data = {"doctype": doctype}
	for field, expr in fields.items():
		doc_data[field] = resolve_expression(expr, context)

	doc = frappe.get_doc(doc_data)
	frappe.log_error("triggered", doc)
	doc.insert()
	frappe.db.commit()

	context["created_doc"] = doc.as_dict()
	context["last_output"] = {"created": doc.name, "doctype": doctype}

	return context


def exec_update_document(node: dict, context: dict) -> dict:
	data = node.get("data", {})
	frappe.error_log("data", data)
	config = data.get("config", {}) if "config" in data else data

	doctype = config.get("doctype")
	if not doctype:
		raise Exception("DocType not specified")

	docname_expr = config.get("docname")
	docname = resolve_expression(docname_expr, context)
	if not docname:
		raise Exception(f"Document name not specified. Expression: '{docname_expr}'")

	fields = config.get("fields", {})

	doc = frappe.get_doc(doctype, docname)

	for field, expr in fields.items():
		value = resolve_expression(expr, context)
		setattr(doc, field, value)

	doc.save()
	frappe.db.commit()

	context["updated_doc"] = doc.as_dict()
	context["last_output"] = {"updated": docname, "doctype": doctype, "fields": list(fields.keys())}

	return context


def exec_delete_document(node: dict, context: dict) -> dict:
	data = node.get("data", {})
	config = data.get("config", {}) if "config" in data else data

	doctype = config.get("doctype")
	if not doctype:
		raise Exception("DocType not specified")

	docname_expr = config.get("docname")
	docname = resolve_expression(docname_expr, context)
	if not docname:
		raise Exception(f"Document name not specified. Expression: '{docname_expr}'")

	frappe.delete_doc(doctype, docname)
	frappe.db.commit()

	context["last_output"] = {"deleted": docname, "doctype": doctype}

	return context


def exec_http_request(node: dict, context: dict) -> dict:
	data = node.get("data", {})
	config = data.get("config", {}) if "config" in data else data

	method = config.get("method", "GET").upper()
	url = resolve_expression(config.get("url"), context)

	if not url:
		raise Exception("URL not specified")

	headers = {}
	for key, value_expr in config.get("headers", {}).items():
		headers[key] = str(resolve_expression(value_expr, context))

	body = None
	if config.get("body"):
		body_data = {}
		for key, value_expr in config["body"].items():
			body_data[key] = resolve_expression(value_expr, context)
		body = body_data

	response = requests.request(
		method=method, url=url, headers=headers, json=body if body else None, timeout=30
	)

	try:
		response_data = response.json()
	except ValueError:
		response_data = response.text

	context["http"] = {"status_code": response.status_code, "response": response_data}

	context["last_output"] = {"status_code": response.status_code, "response": response_data}

	return context


def exec_if_condition(node: dict, context: dict) -> dict:
	return context


def exec_set_variable(node: dict, context: dict) -> dict:
	data = node.get("data", {})
	config = data.get("config", {}) if "config" in data else data

	if "vars" not in context:
		context["vars"] = {}

	variables = config.get("variables", {})
	for var_name, expr in variables.items():
		if expr == "{{now}}":
			from frappe.utils import now

			value = now()
		else:
			value = resolve_expression(expr, context)

		context["vars"][var_name] = value

	context["last_output"] = {"variables_set": list(variables.keys())}

	return context


def exec_delay(node: dict, context: dict) -> dict:
	data = node.get("data", {})
	config = data.get("config", {}) if "config" in data else data

	duration = int(config.get("duration", 0))
	unit = config.get("unit", "seconds")

	if unit == "minutes":
		duration *= 60
	elif unit == "hours":
		duration *= 3600

	if duration > 0:
		time.sleep(duration)

	context["last_output"] = {"delayed": f"{duration} seconds"}

	return context


def exec_loop(node: dict, context: dict) -> dict:
	data = node.get("data", {})
	config = data.get("config", {}) if "config" in data else data

	items_expr = config.get("items")
	items = resolve_expression(items_expr, context)
	item_var = config.get("item_variable", "item")

	if not isinstance(items, list):
		items = []

	context["loop"] = {"items": items, "current_index": 0, "total": len(items), "item_variable": item_var}

	if items:
		context["vars"] = context.get("vars", {})
		context["vars"][item_var] = items[0]

	context["last_output"] = {"loop_items": len(items)}

	return context


def exec_python_expression(node: dict, context: dict) -> dict:
	data = node.get("data", {})
	config = data.get("config", {}) if "config" in data else data

	expression = config.get("expression", "")
	if not expression:
		raise Exception("Expression required for Python Expression node")

	result = resolve_expression(expression, context)

	output_var = config.get("output_variable", "result")
	context[output_var] = result
	context["last_output"] = {output_var: result}

	return context


def exec_data_transform(node: dict, context: dict) -> dict:
	data = node.get("data", {})
	config = data.get("config", {}) if "config" in data else data

	source = config.get("source", "")
	source_data = resolve_expression(source, context) if source else context

	transform = config.get("transform", "{}")

	result = resolve_expression(transform, {**context, "data": source_data})

	output_var = config.get("output_variable", "transformed_data")
	context[output_var] = result
	context["last_output"] = {output_var: result}

	return context


def exec_filter_array(node: dict, context: dict) -> dict:
	data = node.get("data", {})
	config = data.get("config", {}) if "config" in data else data

	array_expr = config.get("array", "[]")
	array = resolve_expression(array_expr, context)

	if not isinstance(array, list):
		raise Exception("Array must be a list")

	condition = config.get("condition", "True")

	filtered = []
	for item in array:
		item_context = {**context, "item": item}
		if resolve_expression(condition, item_context):
			filtered.append(item)

	context["filtered_array"] = filtered
	context["last_output"] = {"count": len(filtered), "items": filtered}

	return context


def exec_map_array(node: dict, context: dict) -> dict:
	data = node.get("data", {})
	config = data.get("config", {}) if "config" in data else data

	array_expr = config.get("array", "[]")
	array = resolve_expression(array_expr, context)

	if not isinstance(array, list):
		raise Exception("Array must be a list")

	transform = config.get("transform", "item")

	mapped = []
	for item in array:
		item_context = {**context, "item": item}
		result = resolve_expression(transform, item_context)
		mapped.append(result)

	context["mapped_array"] = mapped
	context["last_output"] = {"count": len(mapped), "items": mapped}

	return context


def exec_switch_case(node: dict, context: dict) -> dict:
	data = node.get("data", {})
	config = data.get("config", {}) if "config" in data else data

	switch_value = resolve_expression(config.get("value", ""), context)

	cases = config.get("cases", [])

	matched_case = None
	for case in cases:
		case_value = resolve_expression(case.get("value", ""), context)
		if switch_value == case_value:
			matched_case = case
			break

	context["switch_result"] = {
		"matched": matched_case is not None,
		"case": matched_case.get("value") if matched_case else None,
	}
	context["last_output"] = context["switch_result"]

	return context


def exec_send_notification(node: dict, context: dict) -> dict:
	data = node.get("data", {})
	config = data.get("config", {}) if "config" in data else data

	user = resolve_expression(config.get("user", ""), context)
	message = resolve_expression(config.get("message", ""), context)
	subject = resolve_expression(config.get("subject", "Notification"), context)

	frappe.publish_realtime(event="msgprint", message=message, user=user)

	notification = frappe.get_doc(
		{
			"doctype": "Notification Log",
			"subject": subject,
			"for_user": user,
			"type": "Alert",
			"document_type": config.get("reference_doctype", ""),
			"document_name": config.get("reference_name", ""),
		}
	)
	notification.insert(ignore_permissions=True)
	frappe.db.commit()

	context["last_output"] = {"notification": notification.name}

	return context


def exec_create_comment(node: dict, context: dict) -> dict:
	data = node.get("data", {})
	config = data.get("config", {}) if "config" in data else data

	reference_doctype = config.get("reference_doctype")
	reference_name = resolve_expression(config.get("reference_name"), context)
	content = resolve_expression(config.get("content", ""), context)
	comment_type = config.get("comment_type", "Comment")

	if not reference_doctype or not reference_name:
		raise Exception("Reference DocType and Name required for Create Comment")

	comment = frappe.get_doc(
		{
			"doctype": "Comment",
			"comment_type": comment_type,
			"reference_doctype": reference_doctype,
			"reference_name": reference_name,
			"content": content,
		}
	)
	comment.insert(ignore_permissions=True)
	frappe.db.commit()

	context["last_output"] = {"comment": comment.name}

	return context


def exec_workflow_action(node: dict, context: dict) -> dict:
	data = node.get("data", {})
	config = data.get("config", {}) if "config" in data else data

	doctype = config.get("doctype")
	if not doctype:
		raise Exception("DocType not specified")

	docname = resolve_expression(config.get("docname"), context)
	if not docname:
		raise Exception("Document name not specified")

	action = config.get("action")
	if not action:
		raise Exception("Workflow action not specified")

	doc = frappe.get_doc(doctype, docname)

	apply_workflow(doc, action)

	context["workflow"] = {
		"doctype": doctype,
		"docname": docname,
		"action": action,
		"workflow_state": getattr(doc, "workflow_state", None),
	}

	context["last_output"] = {"workflow_state": context["workflow"]["workflow_state"]}

	return context


def exec_get_doc(node: dict, context: dict) -> dict:
	data = node.get("data", {})
	config = data.get("config", {}) if "config" in data else data

	doctype = config.get("doctype")
	docname = resolve_expression(config.get("docname"), context)

	if not doctype or not docname:
		raise Exception("DocType and Document Name required for Get Document")

	doc = frappe.get_doc(doctype, docname)

	context["fetched_doc"] = doc.as_dict()
	context["last_output"] = {"doctype": doctype, "name": docname, "doc": doc.as_dict()}

	return context


def exec_get_list(node: dict, context: dict) -> dict:
	data = node.get("data", {})
	config = data.get("config", {}) if "config" in data else data

	doctype = config.get("doctype")
	if not doctype:
		raise Exception("DocType required for Get List")

	filters = config.get("filters", {})
	resolved_filters = {}
	for key, value in filters.items():
		resolved_filters[key] = resolve_expression(value, context)

	fields = config.get("fields", ["name"])
	if isinstance(fields, str):
		fields = [f.strip() for f in fields.split(",")]

	limit = int(config.get("limit", 20))

	docs = frappe.get_all(doctype, filters=resolved_filters, fields=fields, limit=limit)

	context["doc_list"] = docs
	context["last_output"] = {"doctype": doctype, "count": len(docs), "docs": docs}

	return context


def exec_submit_doc(node: dict, context: dict) -> dict:
	data = node.get("data", {})
	config = data.get("config", {}) if "config" in data else data

	doctype = config.get("doctype")
	docname = resolve_expression(config.get("docname"), context)

	if not doctype or not docname:
		raise Exception("DocType and Document Name required for Submit Document")

	doc = frappe.get_doc(doctype, docname)
	doc.submit()
	frappe.db.commit()

	context["last_output"] = {"doctype": doctype, "name": docname, "docstatus": doc.docstatus}

	return context


def exec_cancel_doc(node: dict, context: dict) -> dict:
	data = node.get("data", {})
	config = data.get("config", {}) if "config" in data else data

	doctype = config.get("doctype")
	docname = resolve_expression(config.get("docname"), context)

	if not doctype or not docname:
		raise Exception("DocType and Document Name required for Cancel Document")

	doc = frappe.get_doc(doctype, docname)
	doc.cancel()
	frappe.db.commit()

	context["last_output"] = {"doctype": doctype, "name": docname, "docstatus": doc.docstatus}

	return context


NODE_EXECUTORS = {
	"doc_event_trigger": exec_doc_event_trigger,
	"erpnext_doc_event_trigger": exec_doc_event_trigger,
	"whatsapp_incoming_trigger": exec_whatsapp_incoming_trigger,
	"whatsapp_trigger": exec_whatsapp_incoming_trigger,
	"scheduled_trigger": exec_scheduled_trigger,
	"manual_trigger": exec_manual_trigger,
	"send_whatsapp": exec_send_whatsapp,
	"whatsapp_send_template": exec_send_whatsapp,
	"send_email": exec_send_email,
	"create_document": exec_create_document,
	"create_doc": exec_create_document,
	"update_document": exec_update_document,
	"update_doc": exec_update_document,
	"delete_document": exec_delete_document,
	"delete_doc": exec_delete_document,
	"http_request": exec_http_request,
	"if_condition": exec_if_condition,
	"if_else": exec_if_condition,
	"set_variable": exec_set_variable,
	"delay": exec_delay,
	"wait": exec_delay,
	"loop": exec_loop,
	"switch": exec_switch_case,
	"switch_case": exec_switch_case,
	"python_expression": exec_python_expression,
	"transform_data": exec_data_transform,
	"filter_array": exec_filter_array,
	"map_array": exec_map_array,
	"workflow_action": exec_workflow_action,
	"erpnext_workflow_action": exec_workflow_action,
	"apply_workflow": exec_workflow_action,
	"get_doc": exec_get_doc,
	"get_document": exec_get_doc,
	"get_list": exec_get_list,
	"submit_doc": exec_submit_doc,
	"submit_document": exec_submit_doc,
	"cancel_doc": exec_cancel_doc,
	"cancel_document": exec_cancel_doc,
	"send_notification": exec_send_notification,
	"create_comment": exec_create_comment,
}


def get_node_executor(node_type: str):
	return NODE_EXECUTORS.get(node_type)
