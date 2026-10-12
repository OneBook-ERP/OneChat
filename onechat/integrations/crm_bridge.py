import json
import mimetypes

import frappe
from frappe import _

from onechat.automation.engine import stop_for_agent
from onechat.inbox import accounts
from onechat.inbox.conversations import CONTACT, MESSAGE, find_contact, outgoing_status, render, reopen
from onechat.integrations import frappe_crm, links

LEAD = "CRM Lead"
DEAL = "CRM Deal"
REFERENCES = (LEAD, DEAL)
CRM_ROLES = ("System Manager", "Sales Manager", "Sales User")
TEMPLATE = "WhatsApp Templates"
ACCOUNT = "OneChat Account"
FIELDS = (
	"name",
	"type",
	"to",
	"from",
	"content_type",
	"message_type",
	"attach",
	"template",
	"use_template",
	"message_id",
	"is_reply",
	"reply_to_message_id",
	"creation",
	"message",
	"status",
	"reference_doctype",
	"reference_name",
	"template_parameters",
	"template_header_parameters",
	"profile_name",
	"error_message",
	"whatsapp_contact",
)
STATUS = {"sent": "Sent", "success": "Sent", "delivered": "Delivered", "read": "Read", "failed": "Failed"}
MEDIA = {"image": "image/jpeg", "video": "video/mp4", "audio": "audio/ogg", "document": "application/pdf"}
HEADER = {"TEXT": "Text", "IMAGE": "Image", "DOCUMENT": "Document", "VIDEO": "Video"}
BUTTON = {
	"Quick Reply": "Quick Reply",
	"Call Phone": "Phone Number",
	"Visit Website": "URL",
	"Flow": "Quick Reply",
}


def active():
	return frappe_crm.shared()


def require_active():
	if not active():
		frappe.throw(_("WhatsApp is not connected to Frappe CRM on this site."))


def require_role():
	if not set(CRM_ROLES) & set(frappe.get_roles()):
		frappe.throw(_("Only sales users can access WhatsApp features."), frappe.PermissionError)


def authorize(doctype, name):
	require_role()
	if doctype not in REFERENCES:
		frappe.throw(_("WhatsApp chats can only be opened from CRM leads and deals."), frappe.PermissionError)
	if not frappe.db.exists(doctype, name):
		frappe.throw(_("{0} {1} does not exist.").format(_(doctype), name), frappe.DoesNotExistError)
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")
	return doc


def scope(doc):
	refs = [(doc.doctype, doc.name)]
	if doc.doctype == DEAL and doc.get("lead") and frappe.has_permission(LEAD, doc=doc.lead):
		refs.append((LEAD, doc.lead))
	return refs


def contacts_of(refs, doc):
	found = []
	for doctype, name in refs:
		found += links.contacts_for(doctype, name)
	if not found and doc.get("mobile_no"):
		contact = find_contact(doc.mobile_no)
		if contact:
			found.append(contact)
	return list(dict.fromkeys(found))


def fetch(refs, contacts):
	table = frappe.qb.DocType(MESSAGE)
	condition = table.whatsapp_contact.isin(contacts) if contacts else None
	for doctype, name in refs:
		pair = (table.reference_doctype == doctype) & (table.reference_name == name)
		condition = pair if condition is None else condition | pair
	return (
		frappe.qb.from_(table)
		.select(*[table[field] for field in FIELDS])
		.where(condition)
		.orderby(table.creation)
		.orderby(table.name)
		.run(as_dict=True)
	)


def messages_for(refs, doc):
	return fetch(refs, contacts_of(refs, doc))


def template_of(name, cache):
	if name not in cache:
		cache[name] = (
			frappe.get_cached_doc(TEMPLATE, name) if name and frappe.db.exists(TEMPLATE, name) else None
		)
	return cache[name]


def sender_name(row, names):
	if row.type != "Incoming":
		return _("You")
	if row.profile_name:
		return row.profile_name
	if row.whatsapp_contact not in names:
		names[row.whatsapp_contact] = frappe.db.get_value(CONTACT, row.whatsapp_contact, "contact_name")
	return names[row.whatsapp_contact] or row["from"]


def classic(rows, doctype, name):
	templates, names = {}, {}
	for row in rows:
		row.reference_doctype, row.reference_name = doctype, name
		row.from_name = sender_name(row, names)
		template = row.message_type == "Template" and template_of(row.template, templates)
		if template:
			row.template_name = template.template_name
			row.template = render(template.template, row.template_parameters)
			row.header = render(template.header, row.template_header_parameters)
			row.footer = template.footer

	by_id = {row.message_id: row for row in rows if row.message_id and row.content_type != "reaction"}
	for row in rows:
		if row.content_type == "reaction" and by_id.get(row.reply_to_message_id):
			by_id[row.reply_to_message_id].reaction = row.message
	for row in rows:
		replied = row.is_reply and by_id.get(row.reply_to_message_id)
		if replied:
			row.reply_message = replied.template if replied.message_type == "Template" else replied.message
			row.header = replied.get("header") or ""
			row.footer = replied.get("footer") or ""
			row.reply_to = replied.name
			row.reply_to_type = replied.type
			row.reply_to_from = replied.from_name
	return [row for row in rows if row.content_type != "reaction"]


def mime_of(row):
	if row.content_type in MEDIA:
		return (row.attach and mimetypes.guess_type(row.attach)[0]) or MEDIA[row.content_type]
	return ""


def modern(rows, doctype, name):
	out = []
	for row in rows:
		reaction = row.content_type == "reaction"
		out.append(
			frappe._dict(
				name=row.name,
				direction=row.type or "Outgoing",
				creation=row.creation,
				message="" if reaction else row.message,
				status=STATUS.get((row.status or "").lower(), "Pending"),
				to=row.to if row.type == "Outgoing" else "",
				**{"from": row["from"] if row.type == "Incoming" else ""},
				mime_type=mime_of(row),
				media_url=row.attach if row.content_type in MEDIA else None,
				is_template=row.message_type == "Template",
				whatsapp_template=row.template,
				message_id=row.message_id,
				context_message_id=row.reply_to_message_id if (row.is_reply or reaction) else None,
				reference_doctype=doctype,
				reference_docname=name,
				template_body_parameters=row.template_parameters,
				template_header_parameters=row.template_header_parameters,
				reaction=row.message if reaction else None,
				error_message=row.error_message,
			)
		)
	out = fold_reactions(out)
	render_templates(out)
	resolve_replies(out)
	attach_files(out)
	return out


def fold_reactions(messages):
	targets, kept = {}, []
	for message in messages:
		if message.reaction is None or not message.context_message_id:
			kept.append(message)
			continue
		target = targets.setdefault(message.context_message_id, {})
		if message.reaction:
			target[message.direction] = message.reaction
		else:
			target.pop(message.direction, None)
	for message in kept:
		found = targets.get(message.message_id, {})
		message.reactions = [{"emoji": emoji, "direction": direction} for direction, emoji in found.items()]
	return kept


def buttons_of(template):
	return [
		{
			"button_type": BUTTON.get(button.button_type, "Quick Reply"),
			"button_text": button.button_label,
			"url": button.website_url,
			"phone_number": button.phone_number,
		}
		for button in template.get("buttons") or []
		if button.get("is_active", 1)
	]


def render_templates(messages):
	cache = {}
	for message in messages:
		template = message.is_template and template_of(message.whatsapp_template, cache)
		if not template:
			continue
		message.template_name = template.template_name
		message.template = render(template.template, message.template_body_parameters)
		message.header = render(template.header, message.template_header_parameters)
		message.footer = template.footer
		message.buttons = buttons_of(template)


def resolve_replies(messages):
	by_id = {message.message_id: message for message in messages if message.message_id}
	for message in messages:
		replied = by_id.get(message.context_message_id)
		if not replied:
			continue
		message.reply_message = replied.template if replied.is_template else replied.message
		message.reply_to = replied.name
		message.reply_to_direction = replied.direction


def attach_files(messages):
	urls = list({message.media_url for message in messages if message.media_url})
	if not urls:
		return
	files = {
		row.file_url: row
		for row in frappe.get_all(
			"File", filters={"file_url": ["in", urls]}, fields=["file_url", "file_name", "file_size"]
		)
	}
	for message in messages:
		found = files.get(message.media_url)
		if found:
			message.file_name = found.file_name
			message.file_size = found.file_size


def contact_for(doc, to):
	contact = find_contact(to) if to else None
	if not contact:
		linked = contacts_of(scope(doc), doc)
		contact = linked[0] if linked else None
	if not contact:
		if not to:
			frappe.throw(_("{0} has no mobile number to message.").format(doc.name))
		contact = (
			frappe.get_doc(
				{
					"doctype": CONTACT,
					"contact_name": doc.get("lead_name") or doc.get("organization") or to,
					"mobile_no": to,
					"conversation_status": outgoing_status(),
				}
			)
			.insert(ignore_permissions=True)
			.name
		)
	if not links.has(contact, doc.doctype, doc.name):
		links.add(contact, doc.doctype, doc.name)
	return contact


def deliver(doc, to, message=None, attach=None, content_type="text", reply_to=None, template=None):
	contact = contact_for(doc, to)
	reopen(frappe.get_doc(CONTACT, contact))
	outgoing = frappe.new_doc(MESSAGE)
	outgoing.update(
		{
			"type": "Outgoing",
			"whatsapp_account": accounts.account_for(contact),
			"source": "Agent",
			"to": frappe.db.get_value(CONTACT, contact, "mobile_no"),
			"reference_doctype": CONTACT,
			"reference_name": contact,
		}
	)
	if template:
		outgoing.update(
			{
				"message_type": "Template",
				"use_template": 1,
				"template": template,
				"message": "Template message",
				"content_type": "text",
			}
		)
		outgoing.flags.custom_ref_doc = doc.as_dict()
	else:
		outgoing.update(
			{
				"message_type": "Manual",
				"message": message or "",
				"attach": attach,
				"content_type": content_type or "text",
			}
		)
	if reply_to:
		replied = frappe.db.get_value(MESSAGE, reply_to, "message_id")
		if replied:
			outgoing.is_reply = 1
			outgoing.reply_to_message_id = replied
	outgoing.insert(ignore_permissions=True)
	stop_for_agent(contact)
	return outgoing.name


def react(name, emoji):
	require_active()
	require_role()
	if not frappe.db.exists(MESSAGE, name):
		frappe.throw(_("Referenced WhatsApp message does not exist."), frappe.DoesNotExistError)
	target = frappe.get_doc(MESSAGE, name)
	contact = target.whatsapp_contact
	if not any(
		doctype in REFERENCES and frappe.has_permission(doctype, doc=link)
		for doctype, link in ((row.doctype, row.name) for row in links.of(contact))
	):
		frappe.throw(_("Not permitted to access the referenced WhatsApp message."), frappe.PermissionError)
	if not target.message_id:
		frappe.throw(_("WhatsApp has not acknowledged this message yet."))
	reaction = frappe.new_doc(MESSAGE)
	reaction.update(
		{
			"type": "Outgoing",
			"whatsapp_account": accounts.account_for(contact),
			"source": "Agent",
			"to": frappe.db.get_value(CONTACT, contact, "mobile_no"),
			"reference_doctype": CONTACT,
			"reference_name": contact,
			"message": emoji,
			"content_type": "reaction",
			"reply_to_message_id": target.message_id,
		}
	)
	reaction.insert(ignore_permissions=True)
	return reaction.name


def publish(doc, contact):
	if not active() or not contact:
		return
	for row in links.of(contact):
		if row.doctype not in REFERENCES:
			continue
		frappe.publish_realtime(
			"whatsapp_message",
			{"reference_doctype": row.doctype, "reference_name": row.name, "reference_docname": row.name},
			doctype=row.doctype,
			docname=row.name,
			after_commit=True,
		)


@frappe.whitelist()
def is_whatsapp_installed():
	return active()


@frappe.whitelist()
def is_whatsapp_enabled():
	if not active():
		return False
	account = accounts.default_outgoing()
	return bool(account) and frappe.db.get_value(ACCOUNT, account, "status") == "Active"


@frappe.whitelist()
def get_whatsapp_messages(reference_doctype: str, reference_name: str):
	if not active():
		return []
	doc = authorize(reference_doctype, reference_name)
	return classic(messages_for(scope(doc), doc), reference_doctype, reference_name)


@frappe.whitelist()
def create_whatsapp_message(
	reference_doctype: str,
	reference_name: str,
	message: str | None = None,
	to: str | None = None,
	attach: str | None = None,
	reply_to: str | None = None,
	content_type: str = "text",
):
	require_active()
	doc = authorize(reference_doctype, reference_name)
	return deliver(doc, to, message or attach, attach, content_type, reply_to)


@frappe.whitelist()
def send_whatsapp_template(reference_doctype: str, reference_name: str, template: str, to: str):
	require_active()
	return deliver(authorize(reference_doctype, reference_name), to, template=template)


@frappe.whitelist()
def react_on_whatsapp_message(emoji: str, reply_to_name: str):
	return react(reply_to_name, emoji)


@frappe.whitelist()
def get_messages(references: str):
	if not active():
		return []
	pairs = [tuple(pair) for pair in (frappe.parse_json(references or "[]") or []) if len(pair) == 2]
	docs = [authorize(doctype, name) for doctype, name in dict.fromkeys(pairs)]
	if not docs:
		return []
	refs = list(dict.fromkeys(ref for doc in docs for ref in scope(doc)))
	contacts = list(dict.fromkeys(contact for doc in docs for contact in contacts_of(scope(doc), doc)))
	return modern(fetch(refs, contacts), docs[0].doctype, docs[0].name)


@frappe.whitelist()
def send_message(
	to: str,
	message: str = "",
	attach: str | None = None,
	content_type: str = "text",
	reply_to: str | None = None,
	reference_doctype: str | None = None,
	reference_docname: str | None = None,
):
	require_active()
	if not (message or "").strip() and not attach:
		frappe.throw(_("Cannot send an empty message."))
	return deliver(
		authorize(reference_doctype, reference_docname), to, message, attach, content_type, reply_to
	)


@frappe.whitelist()
def react_to_message(message: str, emoji: str):
	return react(message, emoji)


@frappe.whitelist()
def send_template(
	template: str, to: str, reference_doctype: str | None = None, reference_docname: str | None = None
):
	require_active()
	return deliver(authorize(reference_doctype, reference_docname), to, template=template)


@frappe.whitelist()
def get_sendable_templates(reference_doctype: str):
	if not active():
		return []
	require_role()
	templates = frappe.get_all(
		TEMPLATE,
		filters={"status": "APPROVED"},
		or_filters=[["for_doctype", "=", reference_doctype], ["for_doctype", "is", "not set"]],
		fields=[
			"name",
			"template_name",
			"template",
			"footer",
			"header",
			"header_type",
			"for_doctype",
			"language_code",
		],
		order_by="modified desc",
	)
	return [
		{
			"name": row.name,
			"template_label": row.template_name,
			"template_name": row.template_name,
			"message": row.template,
			"footer": row.footer,
			"header_text": row.header if row.header_type == "TEXT" else None,
			"header_type": HEADER.get(row.header_type),
			"reference_doctype": row.for_doctype,
			"language": row.language_code,
			"buttons": buttons_of(frappe.get_cached_doc(TEMPLATE, row.name)),
			"template_variables": [],
		}
		for row in templates
	]


def notify_crm(doc, contact):
	if doc.type != "Incoming" or doc.content_type in ("reaction", "comment") or not contact or not active():
		return
	try:
		from crm.api.doc import get_assigned_users
		from crm.fcrm.doctype.crm_notification.crm_notification import notify_user
	except ImportError:
		return

	channel = doc.get("channel") or "WhatsApp"
	for row in links.of(contact):
		if row.doctype not in REFERENCES:
			continue
		text = (
			'<div class="mb-2 leading-5 text-ink-gray-5">'
			f'<span class="font-medium text-ink-gray-9">{_("You")}</span> '
			f"<span>{_('received a {0} message in {1}').format(channel, _('CRM lead') if row.doctype == LEAD else _('CRM deal'))}</span> "
			f'<span class="font-medium text-ink-gray-9">{frappe.utils.escape_html(row.name)}</span>'
			"</div>"
		)
		for user in get_assigned_users(row.doctype, row.name):
			notify_user(
				{
					"owner": doc.owner,
					"assigned_to": user,
					"notification_type": "WhatsApp",
					"message": doc.message,
					"notification_text": text,
					"reference_doctype": MESSAGE,
					"reference_docname": doc.name,
					"redirect_to_doctype": row.doctype,
					"redirect_to_docname": row.name,
				}
			)


def on_message(doc, method=None):
	contact = doc.get("whatsapp_contact")
	publish(doc, contact)
	try:
		notify_crm(doc, contact)
	except Exception:
		frappe.log_error(title="OneChat CRM notification", reference_doctype=MESSAGE, reference_name=doc.name)


def on_status(doc, method=None):
	if doc.has_value_changed("status"):
		publish(doc, doc.get("whatsapp_contact"))
