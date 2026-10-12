import frappe

from onechat import integrations
from onechat.integrations import links

PHONE_FIELDS = ("whatsapp_no", "mobile_no", "mobile", "contact_mobile", "phone", "phone_no")
CONTACT_DOCTYPE = "Contact"


def numbers_of(doc):
	return list(dict.fromkeys(str(doc.get(field)).strip() for field in PHONE_FIELDS if doc.get(field)))


def contact_numbers(doc):
	found = numbers_of(doc)
	for row in doc.get("phone_nos") or []:
		phone = row.get("phone") if isinstance(row, dict) else getattr(row, "phone", None)
		if phone:
			found.append(str(phone).strip())
	return list(dict.fromkeys(found))


def contact_targets(doc):
	linkable = integrations.link_doctypes()
	out = []
	for row in doc.get("links") or []:
		doctype = row.get("link_doctype") if isinstance(row, dict) else getattr(row, "link_doctype", None)
		name = row.get("link_name") if isinstance(row, dict) else getattr(row, "link_name", None)
		if doctype in linkable and name:
			out.append((doctype, name))
	return out


def link_record(doctype, name, numbers):
	if (
		not numbers
		or integrations.setting("disable_auto_link")
		or doctype not in integrations.link_doctypes()
	):
		return []
	from onechat.inbox.conversations import find_contact, publish

	linked = []
	for number in numbers:
		contact = find_contact(number)
		if not contact or contact in linked or links.has(contact, doctype, name):
			continue
		links.add(contact, doctype, name)
		integrations.linked(contact, doctype, name)
		publish(contact)
		linked.append(contact)
	return linked


def handle(doctype, name, doc):
	if doctype == CONTACT_DOCTYPE:
		numbers = contact_numbers(doc)
		return [
			contact
			for target in contact_targets(doc)
			for contact in link_record(target[0], target[1], numbers)
		]
	return link_record(doctype, name, numbers_of(doc))


def record_created(doc, method=None):
	try:
		handle(doc.doctype, doc.name, doc)
	except Exception:
		frappe.log_error(title=f"OneChat auto-link: {doc.doctype} {doc.name}")


def remote_event(doctype, name, event, doc):
	if (doctype == CONTACT_DOCTYPE and event == "on_update") or (
		doctype != CONTACT_DOCTYPE and event == "after_insert"
	):
		try:
			handle(doctype, name, frappe._dict(doc))
		except Exception:
			frappe.log_error(title=f"OneChat auto-link: {doctype} {name}")
