import frappe
from frappe import _
from frappe.desk.form.utils import get_pdf_link

from onechat.utils import get_whatsapp_account


@frappe.whitelist(methods=["POST"])
def get_authorized_pdf_link(doctype: str, docname: str, print_format: str | None = None):
	doc = frappe.get_doc(doctype, docname)
	doc.check_permission("read")
	key = doc.get_document_share_key()
	frappe.db.commit()

	if not print_format:
		if doc.get("custom"):
			if doc.get("default_print_format"):
				print_format = doc.default_print_format
		else:
			default_print_format = frappe.db.get_value(
				"Property Setter",
				filters={"doc_type": doctype, "property": "default_print_format"},
				fieldname="value",
			)
			print_format = default_print_format if default_print_format else "Standard"

	link = get_pdf_link(doctype, docname, print_format=print_format)
	return f"{link}&key={key}"


@frappe.whitelist(methods=["POST"])
def send_document_print_format(
	doctype: str,
	docname: str,
	wh_print_format: str | None = None,
	no_letterhead: int | str = 0,
	mobile: str | int | None = None,
):
	doc = frappe.get_doc(doctype, docname)
	doc.check_permission("read")
	if not frappe.has_permission("OneChat Message", "create"):
		frappe.throw(_("You don't have permission to send WhatsApp messages."), frappe.PermissionError)
	key = doc.get_document_share_key()
	frappe.db.commit()

	print_format = "Standard"
	if doc.get("custom"):
		if doc.get("default_print_format"):
			print_format = doc.default_print_format
	else:
		default_print_format = frappe.db.get_value(
			"Property Setter",
			filters={"doc_type": doctype, "property": "default_print_format"},
			fieldname="value",
		)
		print_format = default_print_format if default_print_format else print_format

	if wh_print_format:
		print_format = wh_print_format

	link = get_pdf_link(doctype, docname, print_format=print_format)
	filename = f"{doc.name}.pdf"
	url = f"{frappe.utils.get_url()}{link}&key={key}"

	wh_mes = frappe.new_doc("OneChat Message")
	wh_mes.type = "Outgoing"
	wh_mes.content_type = "document"
	wh_mes.message = filename
	wh_mes.attach = url
	wh_mes.to = mobile or doc.mobile_no
	wh_mes.whatsapp_account = get_whatsapp_account(account_type="Outgoing").name
	wh_mes.insert(ignore_permissions=True)
	frappe.db.commit()
	return {"status": "success", "message": "WhatsApp message queued"}
