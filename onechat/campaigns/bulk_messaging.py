import json

import frappe
from frappe import _
from frappe.utils import cint

from onechat.api_types import JSON


@frappe.whitelist()
def get_progress(name: str):
	doc = frappe.get_doc("Bulk WhatsApp Message", name)
	doc.check_permission("read")
	return doc.get_progress()


@frappe.whitelist()
def retry_failed(name: str):
	doc = frappe.get_doc("Bulk WhatsApp Message", name)
	doc.check_permission("write")
	doc.retry_failed()
	return True


@frappe.whitelist()
def import_recipients(
	list_name: str,
	doctype: str,
	mobile_field: str,
	name_field: str | None = None,
	filters: JSON = None,
	limit: int | str | None = None,
	data_fields: JSON = None,
):
	from onechat.workspace.session import require

	require("WhatsApp Recipient List", "write")
	if filters and isinstance(filters, str):
		filters = json.loads(filters)

	if data_fields and isinstance(data_fields, str):
		data_fields = json.loads(data_fields)

	doc = frappe.get_doc("WhatsApp Recipient List", list_name)
	doc.check_permission("write")
	if not frappe.has_permission(doctype, "read"):
		frappe.throw(_("You don't have permission to read {0}.").format(_(doctype)), frappe.PermissionError)

	count = doc.import_list_from_doctype(doctype, mobile_field, name_field, filters, limit, data_fields)
	doc.save()

	return count


FILE_LIMIT = 5 * 1024 * 1024
ROW_LIMIT = 20000


def cell(value):
	if value is None:
		return ""
	if isinstance(value, float) and value.is_integer():
		return str(int(value))
	return str(value).strip()


def file_rows(filename, content):
	from frappe.utils.csvutils import read_csv_content
	from frappe.utils.xlsxutils import read_xls_file_from_attached_file, read_xlsx_file_from_attached_file

	extension = (filename or "").rsplit(".", 1)[-1].lower()
	if extension == "csv":
		return read_csv_content(content)
	if extension == "xlsx":
		return read_xlsx_file_from_attached_file(fcontent=content)
	if extension == "xls":
		return read_xls_file_from_attached_file(content)
	frappe.throw(_("Upload a CSV or Excel file (.csv, .xlsx or .xls)."))


@frappe.whitelist(methods=["POST"])
def read_recipient_file(file_url: str):
	from onechat.workspace.session import can

	if not (can("WhatsApp Recipient List", "create") or can("WhatsApp Recipient List", "write")):
		frappe.throw(_("Your role can't edit recipient lists."), frappe.PermissionError)
	name = frappe.db.get_value("File", {"file_url": file_url, "owner": frappe.session.user}, "name")
	if not name:
		frappe.throw(_("Upload the file again."))
	file = frappe.get_doc("File", name)
	try:
		if cint(file.file_size) > FILE_LIMIT:
			frappe.throw(_("The file is larger than 5 MB. Split it into smaller files."))
		rows = [[cell(value) for value in row] for row in file_rows(file.file_name, file.get_content()) or []]
	finally:
		file.delete(ignore_permissions=True)
	rows = [row for row in rows if any(row)]
	if len(rows) < 2:
		frappe.throw(_("The file needs a header row and at least one recipient row."))
	width = max(len(row) for row in rows)
	headers = []
	for index, value in enumerate(rows[0] + [""] * (width - len(rows[0]))):
		label = value or _("Column {0}").format(index + 1)
		while label in headers:
			label = f"{label} {index + 1}"
		headers.append(label)
	body = [row + [""] * (width - len(row)) for row in rows[1:]]
	return {
		"headers": headers,
		"rows": body[:ROW_LIMIT],
		"total": len(body),
		"truncated": len(body) > ROW_LIMIT,
	}


def schedule_bulk_messages():
	bulk_messages = frappe.get_all(
		"Bulk WhatsApp Message",
		filters={"status": "Queued", "docstatus": 1},
		fields=["name", "recipient_count", "sent_count", "skipped_count"],
	)

	for bulk in bulk_messages:
		if cint(bulk.sent_count) + cint(bulk.skipped_count) < cint(bulk.recipient_count):
			continue

		failed_count = frappe.db.count(
			"OneChat Message", {"bulk_message_reference": bulk.name, "status": "Failed"}
		)
		status = "Partially Failed" if failed_count else "Completed"
		frappe.db.set_value("Bulk WhatsApp Message", bulk.name, "status", status)
