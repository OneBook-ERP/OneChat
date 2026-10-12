import frappe
from frappe import _

from onechat import integrations
from onechat.inbox.conversations import CONTACT, find_contact, guard
from onechat.inbox.visibility import check as check_visible
from onechat.integrations import connection, links
from onechat.workspace.session import can_use_app

PHONE_FIELDS = ("whatsapp_no", "mobile_no", "mobile", "contact_mobile", "phone", "phone_no")


def boot_session(bootinfo):
	if frappe.session.user == "Guest":
		return

	try:
		from onechat.integrations.payments import PAYABLE, desk_available

		if desk_available():
			bootinfo.onechat_payments = {"doctypes": list(PAYABLE)}
	except Exception:
		frappe.log_error(title="OneChat desk payments boot")

	if not can_use_app():
		return

	bootinfo.onechat = {"doctypes": sorted(integrations.link_doctypes())}


def visible(contact):
	try:
		check_visible(contact)
		return True
	except frappe.PermissionError:
		return False


def resolve(doctype, name):
	source = connection.source_for(doctype)
	doc = source.get_doc(doctype, name)
	if not doc:
		frappe.throw(_("{0} {1} was not found.").format(_(doctype), name))
	number = next((doc.get(field) for field in PHONE_FIELDS if doc.get(field)), None)
	title = links.describe(doctype, name).get("title") or name
	if not number:
		frappe.throw(_("{0} has no mobile number to message on WhatsApp.").format(frappe.bold(title)))

	contact = find_contact(number)
	if contact:
		if not links.has(contact, doctype, name):
			links.add(contact, doctype, name)
		return contact

	created = frappe.get_doc(
		{
			"doctype": CONTACT,
			"contact_name": title,
			"mobile_no": number,
			"reference_doctype": doctype,
			"reference_docname": name,
		}
	)
	created.insert(ignore_permissions=True)
	return created.name


@frappe.whitelist()
def chats(doctype: str, name: str):
	guard()

	if doctype not in integrations.link_doctypes():
		frappe.throw(_("{0} records can't be linked to WhatsApp conversations.").format(_(doctype)))
	if not connection.source_for(doctype).remote:
		frappe.has_permission(doctype, doc=name, throw=True)

	found = [contact for contact in links.contacts_for(doctype, name) if visible(contact)]
	if not found:
		found = [resolve(doctype, name)]

	rows = frappe.get_all(
		CONTACT,
		filters={"name": ["in", found]},
		fields=[
			"name",
			"contact_name",
			"mobile_no",
			"last_message_at",
			"last_message",
			"conversation_status",
		],
		order_by="last_message_at desc",
	)
	for row in rows:
		row.main = any(
			item.main and (item.doctype, item.name) == (doctype, name) for item in links.of(row.name)
		)
	return rows


@frappe.whitelist()
def chat_count(doctype: str, name: str):
	guard()
	if doctype not in integrations.link_doctypes():
		return 0
	return len([contact for contact in links.contacts_for(doctype, name) if visible(contact)])


@frappe.whitelist()
def open_chat(doctype: str, name: str):
	return chats(doctype, name)[0]["name"]
