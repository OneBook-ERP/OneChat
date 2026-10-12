import frappe
from frappe import _
from frappe.utils.file_manager import save_file

from onechat.workspace.session import require, require_app_user


@frappe.whitelist()
def upload_whatsapp_attachment():
	require_app_user()
	require("OneChat Message", "create")
	files = getattr(frappe.request, "files", None)
	if not files or "file" not in files:
		frappe.throw(_("No file provided."))

	file_obj = files["file"]
	content = file_obj.stream.read()
	if not content:
		frappe.throw(_("Empty file cannot be uploaded."))

	doctype = frappe.form_dict.get("doctype")
	docname = frappe.form_dict.get("docname")
	is_private = frappe.utils.cint(frappe.form_dict.get("is_private") or 0)

	linked_doctype = doctype if doctype and docname else None
	linked_docname = docname if doctype and docname else None

	saved = save_file(
		file_obj.filename,
		content,
		linked_doctype,
		linked_docname,
		is_private=is_private,
	)
	return {
		"file_url": saved.file_url,
		"file_name": saved.file_name,
		"file_size": saved.file_size,
		"file_id": saved.name,
		"mime_type": saved.file_type,
	}


@frappe.whitelist()
def send_whatsapp_template(reference_doctype: str, reference_name: str, template: str, to: str | int):
	require_app_user()
	require("OneChat Message", "create")
	return send_template_message(reference_doctype, reference_name, template, to)


def send_template_message(reference_doctype, reference_name, template, to):
	doc = frappe.new_doc("OneChat Message")
	doc.update(
		{
			"reference_doctype": reference_doctype,
			"reference_name": reference_name,
			"message_type": "Template",
			"message": "Template message",
			"content_type": "text",
			"use_template": True,
			"template": template,
			"to": to,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


@frappe.whitelist()
def react_on_whatsapp_message(emoji: str, reply_to_name: str):
	require_app_user()
	require("OneChat Message", "create")
	reply_to_doc = frappe.get_doc("OneChat Message", reply_to_name)
	to = (reply_to_doc.type == "Incoming" and reply_to_doc.get("from")) or reply_to_doc.to
	doc = frappe.new_doc("OneChat Message")
	doc.update(
		{
			"reference_doctype": reply_to_doc.reference_doctype,
			"reference_name": reply_to_doc.reference_name,
			"message": emoji,
			"to": to,
			"reply_to_message_id": reply_to_doc.message_id,
			"content_type": "reaction",
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name
