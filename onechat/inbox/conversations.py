import html
import json
import re

import frappe
from frappe import _
from frappe.query_builder import Order
from frappe.query_builder.functions import Count, IfNull
from frappe.utils import add_days, cint, escape_html, get_fullname, now_datetime, strip_html

from onechat import integrations
from onechat.api_types import JSON
from onechat.automation.engine import stop_contact, stop_for_agent
from onechat.inbox import accounts, history, visibility
from onechat.inbox.visibility import check as check_visible
from onechat.integrations import links
from onechat.workspace import numbers
from onechat.workspace.audit import track
from onechat.workspace.session import can_use_app, is_admin, require

CONTACT = "OneChat Contact"
MESSAGE = "OneChat Message"
ACCOUNT = "OneChat Account"
INSTAGRAM = "Instagram"
NOTE = "OneChat Note"
LABEL = "OneChat Label"
CONTACT_LABEL = "OneChat Contact Label"
ROOM = f"doctype:{CONTACT}"

NOTE_FIELDS = ["name", "title", "content", "owner", "creation", "modified"]
LABEL_COLORS = ["gray", "blue", "green", "amber", "red", "violet"]

CONTACT_FIELDS = [
	"name",
	"contact_name",
	"mobile_no",
	"email",
	"profile_image",
	"reference_doctype",
	"reference_docname",
	"assigned_to",
	"team",
	"conversation_status",
	"opted_out",
	"unread_count",
	"last_message",
	"last_message_at",
	"last_message_type",
	"bot_flow",
	"snoozed_until",
	"snoozed_by",
	"sla_due_at",
	"sla_breached",
	"whatsapp_account",
	"channel",
	"instagram_id",
	"instagram_username",
]

STATUSES = {"open": "Open", "pending": "Pending", "resolved": "Resolved"}
MENTION_DAYS = 30
BULK_LIMIT = 200
BULK_ACTIONS = ("assign", "status", "add_label", "remove_label", "read")

MESSAGE_FIELDS = [
	"name",
	"type",
	"status",
	"error_message",
	"content_type",
	"message_type",
	"message",
	"attach",
	"latitude",
	"longitude",
	"template",
	"template_parameters",
	"template_header_parameters",
	"buttons",
	"message_id",
	"is_reply",
	"reply_to_message_id",
	"profile_name",
	"source",
	"flow",
	"flow_response",
	"link_url",
	"is_echo",
	"media_id",
	"reply_to_comment",
	"comment_replied",
	"comment_hidden",
	"comment_auto_hidden",
	"owner",
	"creation",
]

PREVIEW = {
	"image": "Photo",
	"video": "Video",
	"audio": "Voice message",
	"document": "Document",
	"location": "Location",
	"contact": "Contact card",
	"flow": "Form response",
	"interactive": "Interactive message",
	"product": "Product",
	"product_list": "Products",
	"order": "Order",
	"order_details": "Payment request",
	"order_status": "Order update",
	"story_reply": "Replied to your story",
	"story_mention": "Mentioned you in their story",
	"share": "Shared a post",
	"comment": "Commented on your post",
	"comment_reply": "Replied to a comment",
}


def digits(number):
	return re.sub(r"\D", "", number or "")


def guard():
	if not can_use_app():
		frappe.throw(_("You do not have access to OneChat."), frappe.PermissionError)
	from onechat.workspace.session import require_read

	require_read(CONTACT)


def preview(message):
	if message.get("message_type") == "Template":
		return _("Template: {0}").format(message.get("template") or "")

	text = strip_html(message.get("message") or "").strip()
	if message.get("content_type") in PREVIEW and not text:
		return _(PREVIEW[message.get("content_type")])

	return text[:140]


def label_map(contacts):
	result = {}
	if not contacts:
		return result

	for row in frappe.get_all(
		CONTACT_LABEL,
		filters={"parenttype": CONTACT, "parentfield": "labels", "parent": ["in", contacts]},
		fields=["parent", "label"],
		order_by="idx asc",
		limit_page_length=0,
	):
		result.setdefault(row.parent, []).append(row.label)

	return result


def with_labels(rows):
	labels = label_map([row.name for row in rows])
	for row in rows:
		row.labels = labels.get(row.name, [])

	return with_links(rows)


def with_links(rows):
	found = links.by_contact([row.name for row in rows])
	for row in rows:
		row.linked = list(
			dict.fromkeys(
				([row.reference_doctype] if row.reference_doctype else []) + found.get(row.name, [])
			)
		)

	return rows


@frappe.whitelist()
def conversations(
	view: str = "all",
	link: str | None = None,
	status: str | None = None,
	label: str | None = None,
	search: str | None = None,
	start: int | str = 0,
	limit: int | str = 30,
	channel: str | None = None,
):
	guard()

	filters = {"disable": 0}
	if channel in ("WhatsApp", INSTAGRAM):
		filters["channel"] = channel
	only = None
	snoozed = True if view == "snoozed" else (None if search or view == "followups" else False)
	if view == "mentions":
		only = set(mentioned_contacts(frappe.session.user))
		if not only:
			return []
	if view == "followups":
		from onechat.inbox.followups import pending_contacts

		only = set(pending_contacts(frappe.session.user))
		if not only:
			return []
	if view == "unread":
		filters["unread_count"] = [">", 0]
	if view == "mine":
		filters["assigned_to"] = frappe.session.user
	if view == "overdue":
		filters["sla_due_at"] = ["<=", now_datetime()]
	if status in STATUSES:
		filters["conversation_status"] = STATUSES[status]
	if label:
		contacts = frappe.get_all(
			CONTACT_LABEL,
			filters={"parenttype": CONTACT, "parentfield": "labels", "label": label},
			pluck="parent",
			distinct=True,
			limit_page_length=0,
		)
		only = set(contacts) if only is None else only & set(contacts)
	if only is not None:
		if not only:
			return []
		filters["name"] = ["in", list(only)]

	table = frappe.qb.DocType(CONTACT)
	query = (
		frappe.qb.from_(table)
		.select(*[table[field] for field in CONTACT_FIELDS])
		.where(where(table, filters, snoozed))
	)
	if link:
		query = query.where(links.with_doctype(table, link))
	if search:
		pattern = f"%{search}%"
		query = query.where(
			table.contact_name.like(pattern)
			| table.mobile_no.like(pattern)
			| table.email.like(pattern)
			| table.instagram_username.like(pattern)
		)

	rows = (
		query.orderby(table.last_message_at, order=Order.desc)
		.orderby(table.modified, order=Order.desc)
		.offset(cint(start))
		.limit(cint(limit) or 30)
		.run(as_dict=True)
	)

	return with_labels(rows)


def where(table, filters, snoozed=False):
	condition = (IfNull(table.channel, "") != INSTAGRAM) | table.last_message_at.isnotnull()
	scope = visibility.shown(table)
	if scope is not None:
		condition = condition & scope
	if snoozed is not None:
		now = now_datetime()
		part = (
			table.snoozed_until > now
			if snoozed
			else (table.snoozed_until.isnull() | (table.snoozed_until <= now))
		)
		condition = part if condition is None else condition & part
	for field, value in filters.items():
		if isinstance(value, list):
			operator, argument = value
			part = {
				">": table[field] > argument,
				"<=": table[field] <= argument,
				"in": table[field].isin(argument),
			}[operator]
		else:
			part = table[field] == value
		condition = part if condition is None else condition & part
	return condition


def count_where(filters, snoozed=False):
	table = frappe.qb.DocType(CONTACT)
	return cint(frappe.qb.from_(table).select(Count("*")).where(where(table, filters, snoozed)).run()[0][0])


@frappe.whitelist()
def counts(channel: str | None = None):
	guard()

	base = {"disable": 0}
	if channel in ("WhatsApp", INSTAGRAM):
		base["channel"] = channel
	me = frappe.session.user
	return {
		"unread": count_where({**base, "unread_count": [">", 0]}),
		"mine": count_where({**base, "assigned_to": me}),
		"mine_unread": count_where({**base, "assigned_to": me, "unread_count": [">", 0]}),
		"open": count_where({**base, "conversation_status": "Open"}),
		"pending": count_where({**base, "conversation_status": "Pending"}),
		"snoozed": count_where(base, snoozed=True),
		"overdue": count_where({**base, "sla_due_at": ["<=", now_datetime()]}),
		"followups": followup_count(me),
		"channels": active_channels(),
	}


def active_channels():
	return sorted(set(frappe.get_all(ACCOUNT, filters={"status": "Active"}, pluck="channel")) - {None, ""})


def followup_count(user):
	from onechat.inbox.followups import pending_contacts

	contacts = pending_contacts(user)
	return count_where({"disable": 0, "name": ["in", contacts]}, snoozed=None) if contacts else 0


@frappe.whitelist()
def conversation(contact: str):
	guard()
	check_visible(contact)

	doc = frappe.get_doc(CONTACT, contact)
	data = {field: doc.get(field) for field in CONTACT_FIELDS}
	data["labels"] = [row.label for row in doc.get("labels") or []]
	data["notes"] = note_rows(
		frappe.get_all(
			NOTE,
			filters={"reference_doctype": CONTACT, "reference_docname": contact},
			fields=NOTE_FIELDS,
			order_by="creation desc",
			limit_page_length=0,
		)
	)
	data["cards"] = integrations.cards(doc)
	data["actions"] = integrations.actions(doc)
	data["links"] = links.public(doc)

	return data


@frappe.whitelist()
def messages(contact: str, before: str | None = None, limit: int | str = 40):
	guard()
	check_visible(contact)
	from onechat.workspace.session import can_read, require_read

	require_read(MESSAGE)

	limit = cint(limit) or 40
	filters = [
		[MESSAGE, "whatsapp_contact", "=", contact],
		[MESSAGE, "content_type", "!=", "reaction"],
	]
	if before:
		filters.append([MESSAGE, "creation", "<", before])

	rows = frappe.get_all(
		MESSAGE, filters=filters, fields=MESSAGE_FIELDS, order_by="creation desc", limit_page_length=limit
	)
	rows.reverse()
	has_more = len(rows) == limit

	note_filters = [[NOTE, "reference_doctype", "=", CONTACT], [NOTE, "reference_docname", "=", contact]]
	if has_more:
		note_filters.append([NOTE, "creation", ">=", rows[0].creation])
	if before:
		note_filters.append([NOTE, "creation", "<", before])

	notes = (
		note_rows(
			frappe.get_all(
				NOTE, filters=note_filters, fields=NOTE_FIELDS, order_by="creation asc", limit_page_length=0
			)
		)
		if can_read(NOTE)
		else []
	)
	items = sorted(enrich(rows) + notes, key=lambda row: row.creation)

	return {"messages": items, "has_more": has_more}


def note_rows(rows):
	for row in rows:
		row.kind = "note"
		row.owner_name = get_fullname(row.owner)

	return rows


def note_row(doc):
	row = frappe._dict({field: doc.get(field) for field in NOTE_FIELDS})
	return note_rows([row])[0]


def note_html(text, names=()):
	lines = []
	for line in text.split("\n"):
		escaped = escape_html(line)
		for name in sorted(names, key=len, reverse=True):
			tag = escape_html(f"@{name}")
			escaped = escaped.replace(tag, f"<strong>{tag}</strong>")
		lines.append(f"<p>{escaped or '<br>'}</p>")
	return "".join(lines)


def mention_names(text, mentions):
	users = [user for user in dict.fromkeys(frappe.parse_json(mentions) or []) if user] if mentions else []
	if not users:
		return {}
	rows = frappe.get_all(
		"OneChat User", filters={"user": ["in", users], "enabled": 1}, fields=["user", "full_name"]
	)
	return {row.user: row.full_name or row.user for row in rows if f"@{row.full_name or row.user}" in text}


def mentioned_contacts(user):
	return frappe.get_all(
		NOTE,
		filters={
			"reference_doctype": CONTACT,
			"mentions": ["like", f'%"{user}"%'],
			"creation": [">=", add_days(now_datetime(), -MENTION_DAYS)],
		},
		pluck="reference_docname",
		distinct=True,
		limit_page_length=0,
	)


def notify_mentions(contact, users, text):
	author = get_fullname(frappe.session.user)
	name = frappe.db.get_value(CONTACT, contact, "contact_name") or contact
	excerpt = text.strip()[:160]
	for user in users:
		if user == frappe.session.user:
			continue
		frappe.get_doc(
			{
				"doctype": "Notification Log",
				"subject": _("{0} mentioned you in a note on {1}").format(author, name),
				"email_content": escape_html(excerpt),
				"for_user": user,
				"from_user": frappe.session.user,
				"type": "Mention",
				"document_type": CONTACT,
				"document_name": contact,
			}
		).insert(ignore_permissions=True)
		frappe.publish_realtime(
			"onechat_mention",
			{"contact": contact, "contact_name": name, "author": author, "text": excerpt},
			user=user,
			after_commit=True,
		)


def note_text(content):
	text = re.sub(r"<br\s*/?>", "\n", content or "", flags=re.I)
	text = re.sub(r"</(p|div|li|h\d)>", "\n", text, flags=re.I)
	return html.unescape(strip_html(text)).strip()


def note_title(text):
	return text.split("\n")[0].strip()[:80]


def can_edit_note(doc):
	return doc.owner == frappe.session.user or is_admin()


@frappe.whitelist()
def save_note(
	contact: str | None = None, content: str | None = None, name: str | None = None, mentions: JSON = None
):
	guard()
	require(NOTE, "write" if name else "create")

	text = (content or "").strip()
	if not text:
		frappe.throw(_("Write something first."))

	named = mention_names(text, mentions)
	previous = set()

	if name:
		doc = frappe.get_doc(NOTE, name)
		if doc.reference_doctype == CONTACT:
			check_visible(doc.reference_docname)
		if not can_edit_note(doc):
			frappe.throw(_("Only the author or an admin can edit this note."), frappe.PermissionError)
		if not doc.title or doc.title == note_title(note_text(doc.content)):
			doc.title = note_title(text)
		previous = set(frappe.parse_json(doc.mentions or "[]") or [])
		doc.content = note_html(text, named.values())
	else:
		if not frappe.db.exists(CONTACT, contact):
			frappe.throw(_("Conversation not found."))
		check_visible(contact)
		doc = frappe.new_doc(NOTE)
		doc.update(
			{
				"title": note_title(text),
				"content": note_html(text, named.values()),
				"reference_doctype": CONTACT,
				"reference_docname": contact,
			}
		)

	doc.mentions = json.dumps(sorted(named)) if named else None
	doc.save(ignore_permissions=True)
	fresh = [user for user in named if user not in previous]
	if fresh:
		notify_mentions(doc.reference_docname, fresh, text)

	return note_row(doc)


@frappe.whitelist()
def delete_note(name: str):
	guard()
	require(NOTE, "delete")

	doc = frappe.get_doc(NOTE, name)
	if doc.reference_doctype == CONTACT:
		check_visible(doc.reference_docname)
	if not can_edit_note(doc):
		frappe.throw(_("Only the author or an admin can delete this note."), frappe.PermissionError)

	doc.delete(ignore_permissions=True)


def publish_note(contact, note, deleted=False):
	visibility.broadcast(
		"onechat_note", {"contact": contact, "note": note, "deleted": deleted}, contact, ROOM
	)


def note_saved(doc, method=None):
	before = doc.get_doc_before_save()
	if (
		before
		and before.reference_doctype == CONTACT
		and before.reference_docname
		and (before.reference_doctype, before.reference_docname)
		!= (doc.reference_doctype, doc.reference_docname)
	):
		publish_note(before.reference_docname, {"name": doc.name, "kind": "note"}, deleted=True)

	if doc.reference_doctype == CONTACT and doc.reference_docname:
		publish_note(doc.reference_docname, note_row(doc))


def note_deleted(doc, method=None):
	if doc.reference_doctype == CONTACT and doc.reference_docname:
		publish_note(doc.reference_docname, {"name": doc.name, "kind": "note"}, deleted=True)


MEDIA_HEADERS = ("IMAGE", "VIDEO", "DOCUMENT")


def enrich(rows):
	ids = [row.message_id for row in rows if row.message_id]
	reactions = {}
	if ids:
		for reaction in frappe.get_all(
			MESSAGE,
			filters={"content_type": "reaction", "reply_to_message_id": ["in", ids]},
			fields=["reply_to_message_id", "message", "type"],
			order_by="creation asc",
		):
			reactions.setdefault(reaction.reply_to_message_id, {})[reaction.type or "Outgoing"] = (
				reaction.message
			)

	reply_ids = [row.reply_to_message_id for row in rows if row.is_reply and row.reply_to_message_id]
	replies = {}
	if reply_ids:
		for reply in frappe.get_all(
			MESSAGE,
			filters={"message_id": ["in", reply_ids]},
			fields=["name", "message_id", "type", "content_type", "message", "message_type", "template"],
		):
			replies[reply.message_id] = {
				"name": reply.name,
				"type": reply.type,
				"content_type": reply.content_type,
				"text": preview(reply),
			}

	templates = {}
	for row in rows:
		row.kind = "message"
		row.reactions = [emoji for emoji in reactions.get(row.message_id, {}).values() if emoji]
		row.reply = replies.get(row.reply_to_message_id) if row.is_reply else None
		if row.message_type == "Template" and row.template:
			if row.template not in templates:
				templates[row.template] = frappe.db.get_value(
					"WhatsApp Templates",
					row.template,
					["template_name", "template", "header", "footer", "header_type", "sample"],
					as_dict=True,
				)
			template = templates[row.template]
			if template:
				row.template_name = template.template_name
				row.template_body = render(template.template, row.template_parameters)
				row.template_header = render(template.header, row.template_header_parameters)
				row.template_footer = template.footer
				if template.header_type in MEDIA_HEADERS:
					row.template_media_type = template.header_type.lower()
					row.template_media = row.attach or template.sample

	links_sent = {}
	for row in rows:
		if row.content_type == "interactive" and row.buttons and "payment_request" in row.buttons:
			try:
				request = json.loads(row.buttons).get("payment_request")
			except ValueError:
				request = None
			if request:
				links_sent[row.name] = request
	if links_sent:
		from onechat.integrations.payments import request_statuses

		statuses = request_statuses(set(links_sent.values()))
		for row in rows:
			if row.name in links_sent:
				row.payment_link = {
					"request": links_sent[row.name],
					"status": statuses.get(links_sent[row.name]) or "",
				}

	asks = [row.name for row in rows if row.content_type == "order_details"]
	if asks:
		from onechat.whatsapp.pay import for_messages

		payments = for_messages(asks)
		for row in rows:
			if row.name in payments:
				row.payment = payments[row.name]

	return rows


def render(text, parameters):
	if not text or not parameters:
		return text

	try:
		values = json.loads(parameters)
	except (TypeError, ValueError):
		return text

	if isinstance(values, dict):
		values = list(values.values())

	for index, value in enumerate(values, start=1):
		text = text.replace("{{" + str(index) + "}}", str(value or ""))

	return text


@frappe.whitelist()
def send(
	contact: str,
	message: str | None = None,
	attach: str | None = None,
	content_type: str = "text",
	reply_to: str | None = None,
):
	guard()
	require(MESSAGE, "create")
	check_visible(contact)

	if not (message or attach):
		frappe.throw(_("Write a message or attach a file."))

	account = accounts.check(contact)
	doc = frappe.get_doc(CONTACT, contact)
	reopen(doc)
	outgoing = frappe.new_doc(MESSAGE)
	outgoing.update(
		{
			"type": "Outgoing",
			"whatsapp_account": account,
			"message_type": "Manual",
			"source": "Agent",
			"to": doc.mobile_no,
			"message": message or "",
			"attach": attach,
			"content_type": content_type or "text",
			"reference_doctype": CONTACT,
			"reference_name": contact,
		}
	)
	if reply_to:
		outgoing.is_reply = 1
		outgoing.reply_to_message_id = frappe.db.get_value(MESSAGE, reply_to, "message_id")

	outgoing.insert(ignore_permissions=True)
	stop_for_agent(contact)

	return single(outgoing.name)


@frappe.whitelist()
def send_template(contact: str, template: str, parameters: JSON = None):
	guard()
	require(MESSAGE, "create")
	check_visible(contact)

	account = accounts.check(contact)
	doc = frappe.get_doc(CONTACT, contact)
	reopen(doc)
	outgoing = frappe.new_doc(MESSAGE)
	outgoing.update(
		{
			"type": "Outgoing",
			"whatsapp_account": account,
			"message_type": "Template",
			"source": "Agent",
			"use_template": 1,
			"template": template,
			"message": "Template message",
			"content_type": "text",
			"to": doc.mobile_no,
			"reference_doctype": CONTACT,
			"reference_name": contact,
		}
	)

	values = frappe.parse_json(parameters) if parameters else None
	if values:
		outgoing.body_param = json.dumps({str(index): value for index, value in enumerate(values, start=1)})

	outgoing.insert(ignore_permissions=True)
	stop_for_agent(contact)

	return single(outgoing.name)


@frappe.whitelist()
def react(message: str, emoji: str):
	guard()
	require(MESSAGE, "create")

	from onechat.whatsapp.message import react_on_whatsapp_message

	return react_on_whatsapp_message(emoji, message)


@frappe.whitelist()
def mark_read(contact: str):
	guard()
	check_visible(contact)

	frappe.db.set_value(CONTACT, contact, "unread_count", 0, update_modified=False)
	publish(contact)
	from onechat.inbox.read_receipts import on_open

	on_open(contact)


@frappe.whitelist()
def assign(contact: str, user: str | None = None):
	guard()
	require(CONTACT, "write")
	check_visible(contact)

	previous = frappe.db.get_value(CONTACT, contact, "assigned_to")
	frappe.db.set_value(CONTACT, contact, "assigned_to", user or None, update_modified=False)
	track(CONTACT, contact, [("assigned_to", previous, user or None)])
	publish(contact, assigned=(user or None) != previous, assigned_by=frappe.session.user)


def status_values(status):
	values = {"conversation_status": status, "resolved_by": None, "resolved_at": None}
	if status == "Resolved":
		values.update({"resolved_by": frappe.session.user, "resolved_at": now_datetime()})

	return values


def reopen(doc):
	if doc.conversation_status == "Resolved":
		frappe.db.set_value(CONTACT, doc.name, status_values("Open"), update_modified=False)
		track(CONTACT, doc.name, [("conversation_status", "Resolved", "Open")])
		from onechat.workspace.webhooks import fire

		fire(doc.name, "reopened")


ALLOW, CONFIRM, BLOCK = "Allow", "Ask to confirm", "Block"


def resolve_config():
	settings = frappe.get_cached_doc("OneChat Settings")
	reasons = [line.strip() for line in (settings.get("resolve_reasons") or "").splitlines() if line.strip()]
	return {
		"require_reason": bool(cint(settings.get("resolve_require_reason"))),
		"require_note": bool(cint(settings.get("resolve_require_note"))),
		"reasons": reasons,
		"when_waiting": settings.get("resolve_when_waiting") or ALLOW,
		"only_owner": bool(cint(settings.get("resolve_only_owner"))),
	}


@frappe.whitelist()
def resolve_rules():
	guard()
	return {**resolve_config(), "is_admin": is_admin()}


def waiting(contact):
	last = frappe.get_all(
		MESSAGE,
		filters={"whatsapp_contact": contact, "content_type": ["!=", "reaction"]},
		fields=["type"],
		order_by="creation desc",
		limit_page_length=1,
	)
	return bool(last) and last[0].type == "Incoming"


def check_resolve(contact, reason, force, note=None):
	rules = resolve_config()
	admin = is_admin()
	if rules["only_owner"] and not admin:
		owner = frappe.db.get_value(CONTACT, contact, "assigned_to")
		if owner and owner != frappe.session.user:
			frappe.throw(
				_("Only the assigned agent or an admin can resolve this chat."), frappe.PermissionError
			)
	if rules["when_waiting"] != ALLOW and waiting(contact):
		if rules["when_waiting"] == BLOCK and not admin:
			frappe.throw(
				_("The customer is waiting for a reply. Reply first, or ask an admin to resolve it.")
			)
		if not cint(force):
			frappe.throw(_("The customer is waiting for a reply. Confirm to resolve anyway."))
	reason = (reason or "").strip()
	if rules["require_reason"]:
		if not reason:
			frappe.throw(_("Choose why this chat is resolved."))
		if rules["reasons"] and reason not in rules["reasons"]:
			frappe.throw(_("Choose one of the resolution reasons."))
	if rules["require_note"] and not strip_html(note or "").strip():
		frappe.throw(_("Write a note about what was done before resolving this chat."))
	return reason


def remember_resolution(contact, reason, note):
	if not (reason or note):
		return
	name = frappe.db.get_value(history.CONVERSATION, {"contact": contact}, "name", order_by="opened_at desc")
	if name:
		frappe.db.set_value(
			history.CONVERSATION,
			name,
			{"resolution_reason": reason or None, "resolution_note": (note or "").strip() or None},
			update_modified=False,
		)


@frappe.whitelist()
def set_status(
	contact: str, status: str, reason: str | None = None, note: str | None = None, force: bool | int | str = 0
):
	guard()
	require(CONTACT, "write")
	check_visible(contact)

	status = STATUSES.get(str(status or "").lower())
	if not status:
		frappe.throw(_("Choose Open, Pending or Resolved."))

	previous = frappe.db.get_value(CONTACT, contact, "conversation_status")
	if status == "Resolved" and previous != "Resolved":
		reason = check_resolve(contact, reason, force, note)
	frappe.db.set_value(CONTACT, contact, status_values(status), update_modified=False)
	changes = [("conversation_status", previous, status)]
	if status == "Resolved" and reason:
		changes.append(("resolution_reason", None, reason))
	track(CONTACT, contact, changes)
	if status == "Pending":
		from onechat.inbox import service

		service.stop_clock(contact)
	if status == "Resolved":
		history.resolved(contact, frappe.session.user)
		remember_resolution(contact, reason, note)
		stop_contact(contact, _("Conversation resolved"))
		if previous != "Resolved":
			from onechat.inbox.service import send_survey

			try:
				send_survey(contact)
			except Exception:
				frappe.log_error(title="OneChat satisfaction survey")
	publish(contact)
	if previous != status:
		from onechat.workspace.webhooks import fire

		fire(contact, "status")
		if previous == "Resolved":
			fire(contact, "reopened")

	return status


@frappe.whitelist()
def quick_replies(search: str | None = None):
	guard()

	or_filters = None
	if search:
		pattern = f"%{search.strip().lstrip('/')}%"
		or_filters = {
			"shortcut": ["like", pattern],
			"title": ["like", pattern],
			"message": ["like", pattern],
		}

	return frappe.get_all(
		"OneChat Quick Reply",
		or_filters=or_filters,
		fields=["name", "shortcut", "title", "message", "attach"],
		order_by="shortcut asc",
		limit_page_length=0,
	)


@frappe.whitelist()
def agents():
	guard()

	return frappe.get_all(
		"OneChat User",
		filters={"enabled": 1},
		fields=["user as name", "full_name", "profile_image as image"],
		order_by="full_name asc",
	)


@frappe.whitelist()
def templates(search: str | None = None):
	guard()

	or_filters = None
	if search:
		or_filters = {"template_name": ["like", f"%{search}%"], "actual_name": ["like", f"%{search}%"]}

	return frappe.get_all(
		"WhatsApp Templates",
		or_filters=or_filters,
		fields=[
			"name",
			"template_name",
			"actual_name",
			"template",
			"header",
			"footer",
			"language_code",
			"category",
			"status",
			"sample_values",
		],
		order_by="template_name asc",
		limit_page_length=50,
	)


def single(name):
	row = frappe.get_all(MESSAGE, filters={"name": name}, fields=MESSAGE_FIELDS)
	return enrich(row)[0] if row else None


def find_contact(number):
	wa_number = digits(number)
	if not wa_number:
		return None

	whatsapp = {"channel": ["!=", INSTAGRAM]}
	name = frappe.db.get_value(CONTACT, {"wa_number": wa_number, **whatsapp})
	if name or len(wa_number) < 10:
		return name

	return frappe.db.get_value(
		CONTACT, {"wa_number": ["like", f"%{wa_number[-10:]}"], **whatsapp}
	) or frappe.db.get_value(CONTACT, {"other_numbers": ["like", f"%{wa_number[-10:]}%"], **whatsapp})


def find_instagram_contact(instagram_id, account=None):
	if not instagram_id:
		return None
	filters = {"channel": INSTAGRAM, "instagram_id": instagram_id}
	if account:
		filters["whatsapp_account"] = account
	return frappe.db.get_value(CONTACT, filters)


def channel_of(message):
	account = message.get("whatsapp_account")
	return (account and frappe.db.get_value(ACCOUNT, account, "channel")) or "WhatsApp"


def ensure_contact(message):
	party = message.get("from") if message.type == "Incoming" else message.to
	if channel_of(message) == INSTAGRAM:
		return ensure_instagram_contact(message, party)

	name = find_contact(party)
	if name:
		return name

	if not digits(party):
		return None

	values = {"doctype": CONTACT, "contact_name": message.profile_name or party, "mobile_no": party}
	if message.type != "Incoming":
		values["conversation_status"] = outgoing_status()
	contact = frappe.get_doc(values)
	contact.insert(ignore_permissions=True)

	return contact.name


def ensure_instagram_contact(message, instagram_id):
	name = find_instagram_contact(instagram_id, message.get("whatsapp_account"))
	if name or not instagram_id:
		return name

	values = {
		"doctype": CONTACT,
		"contact_name": message.profile_name or instagram_id,
		"instagram_id": instagram_id,
		"whatsapp_account": message.get("whatsapp_account"),
	}
	if message.type != "Incoming":
		values["conversation_status"] = outgoing_status()
	contact = frappe.get_doc(values)
	contact.insert(ignore_permissions=True)

	return contact.name


def placeholder_name(name, instagram_id=None):
	name = (name or "").strip()
	if not name or name == instagram_id:
		return True
	# A name made only of digits and phone punctuation is the number standing in for one.
	return bool(digits(name)) and not re.search(r"[^\d\s+().-]", name)


def refresh_name(contact, profile_name):
	profile_name = (profile_name or "").strip()
	if not profile_name:
		return

	row = frappe.db.get_value(CONTACT, contact, ["contact_name", "instagram_id"], as_dict=True)
	if not row or not placeholder_name(row.contact_name, row.instagram_id):
		return

	frappe.db.set_value(CONTACT, contact, "contact_name", profile_name)
	from onechat.workspace.audit import track

	track(CONTACT, contact, [("contact_name", row.contact_name, profile_name)])


def outgoing_status():
	settings = frappe.get_cached_doc("OneChat Settings")
	value = settings.get("outgoing_new_status") if settings.meta.has_field("outgoing_new_status") else None
	return value if value in ("Open", "Pending", "Resolved") else "Pending"


def on_message(doc, method=None):
	contact = (
		doc.get("whatsapp_contact")
		or (doc.reference_name if doc.reference_doctype == CONTACT else None)
		or ensure_contact(doc)
	)
	if not contact:
		return

	if doc.type == "Incoming":
		refresh_name(contact, doc.get("profile_name"))

	from onechat.integrations import frappe_crm

	frappe_crm.on_message(doc, contact)

	refs = {"whatsapp_contact": contact}
	if not doc.reference_doctype:
		refs.update({"reference_doctype": CONTACT, "reference_name": contact})
	frappe.db.set_value(MESSAGE, doc.name, refs, update_modified=False)
	doc.update(refs)

	from onechat.inbox import service

	if doc.type == "Incoming" and doc.content_type != "comment" and service.record_survey(doc, contact):
		publish(contact, doc.name)
		return

	if doc.flags.get("onechat_quiet"):
		return

	surface(doc, contact, unread=not doc.flags.get("onechat_no_unread"))


def surface(doc, contact, unread=True):
	from onechat.inbox import service

	if doc.content_type != "reaction":
		updates = {
			"last_message": preview(doc.as_dict()),
			"last_message_at": doc.creation,
			"last_message_type": doc.type or "Outgoing",
		}
		if doc.type == "Incoming":
			current = frappe.db.get_value(
				CONTACT, contact, ["unread_count", "conversation_status"], as_dict=True
			)
			updates["unread_count"] = cint(current.unread_count) + (1 if unread else 0)
			if current.conversation_status != "Open":
				updates.update(status_values("Open"))
			if current.conversation_status == "Resolved":
				doc.flags.onechat_reopened = True
			if current.conversation_status != "Open":
				doc.flags.onechat_new_chat = True
			if current.conversation_status != "Open":
				track(CONTACT, contact, [("conversation_status", current.conversation_status, "Open")])
		frappe.db.set_value(CONTACT, contact, updates, update_modified=False)
		history.on_message(doc, contact)
		if doc.type == "Incoming":
			if service.needs_reply(doc):
				service.start_clock(contact, doc.creation)
		elif doc.get("source") in service.ANSWERS:
			service.stop_clock(contact)
		if doc.type == "Incoming":
			from onechat.inbox.followups import on_incoming

			try:
				on_incoming(doc, contact)
			except Exception:
				frappe.log_error(title="OneChat follow-ups")

	publish(contact, doc.name, new_chat=bool(doc.flags.onechat_new_chat))
	if doc.flags.onechat_new_chat:
		from onechat.workspace.webhooks import fire

		fire(contact, "status")
		if doc.flags.onechat_reopened:
			fire(contact, "reopened")


def on_status(doc, method=None):
	if not doc.get_doc_before_save():
		return

	attached = doc.has_value_changed("attach") and doc.attach
	if not (attached or doc.has_value_changed("status")):
		return

	contact = doc.whatsapp_contact or frappe.db.get_value(MESSAGE, doc.name, "whatsapp_contact")
	if not contact:
		return

	if attached:
		publish(contact, doc.name)
		return

	visibility.broadcast(
		"onechat_message_status",
		{"contact": contact, "message": doc.name, "status": doc.status, "error_message": doc.error_message},
		contact,
		ROOM,
	)


def publish(contact, message=None, **event):
	row = frappe.db.get_value(CONTACT, contact, CONTACT_FIELDS, as_dict=True)
	if row:
		row.labels = label_map([contact]).get(contact, [])
		with_links([row])
	payload = {"contact": row, **event}
	if message:
		payload["message"] = single(message)

	visibility.broadcast("onechat_inbox", payload, contact, ROOM, removed={"removed": contact})
	if row and event.get("assigned"):
		from onechat.workspace.notifications import notify
		from onechat.workspace.webhooks import fire

		fire(contact, "assigned")
		if row.assigned_to:
			notify(
				row.assigned_to,
				_("{0} was assigned to you").format(row.contact_name or row.mobile_no or contact),
				CONTACT,
				contact,
				"Assignment",
				event.get("assigned_by") or "Administrator",
			)


def ensure_admin():
	if not is_admin():
		frappe.throw(_("Only OneChat admins can manage labels."), frappe.PermissionError)


def label_counts():
	child = frappe.qb.DocType(CONTACT_LABEL)
	rows = (
		frappe.qb.from_(child)
		.select(child.label, Count("*").as_("count"))
		.where((child.parenttype == CONTACT) & (child.parentfield == "labels"))
		.groupby(child.label)
		.run(as_dict=True)
	)

	return {row.label: cint(row.count) for row in rows}


@frappe.whitelist()
def labels(with_counts: int | str = 0):
	guard()

	rows = frappe.get_all(
		LABEL,
		fields=["name", "label_name", "color", "description"],
		order_by="label_name asc",
		limit_page_length=0,
	)
	if cint(with_counts):
		counts = label_counts()
		for row in rows:
			row.count = counts.get(row.name, 0)

	return rows


@frappe.whitelist()
def set_labels(contact: str, labels: JSON = None):
	guard()
	require(CONTACT, "write")
	check_visible(contact)

	if not frappe.db.exists(CONTACT, contact):
		frappe.throw(_("Conversation not found."))

	wanted = list(dict.fromkeys(frappe.parse_json(labels) or [])) if labels else []
	known = set(frappe.get_all(LABEL, filters={"name": ["in", wanted]}, pluck="name")) if wanted else set()
	names = [name for name in wanted if name in known]

	previous = frappe.get_all(
		CONTACT_LABEL,
		filters={"parenttype": CONTACT, "parentfield": "labels", "parent": contact},
		pluck="label",
		order_by="idx asc",
	)
	frappe.db.delete(CONTACT_LABEL, {"parenttype": CONTACT, "parentfield": "labels", "parent": contact})
	for index, name in enumerate(names, start=1):
		frappe.get_doc(
			{
				"doctype": CONTACT_LABEL,
				"parent": contact,
				"parenttype": CONTACT,
				"parentfield": "labels",
				"idx": index,
				"label": name,
			}
		).db_insert()

	track(CONTACT, contact, [("labels", ", ".join(previous), ", ".join(names))])
	publish(contact)
	if sorted(previous) != sorted(names):
		from onechat.workspace.webhooks import fire

		fire(contact, "labels")

	return names


@frappe.whitelist()
def save_label(label_name: str, color: str = "gray", description: str | None = None, name: str | None = None):
	guard()
	require(LABEL, "write" if name else "create")
	ensure_admin()

	label_name = (label_name or "").strip()
	if not label_name:
		frappe.throw(_("Give the label a name."))
	if color not in LABEL_COLORS:
		color = "gray"

	previous = name
	if name and name != label_name:
		if frappe.db.exists(LABEL, label_name):
			frappe.throw(_("A label called {0} already exists.").format(label_name))
		frappe.rename_doc(LABEL, name, label_name, force=True)
		name = label_name

	doc = frappe.get_doc(LABEL, name) if name else frappe.new_doc(LABEL)
	doc.update({"label_name": label_name, "color": color, "description": description or None})
	doc.save(ignore_permissions=True)

	payload = {"renamed": [previous, doc.name]} if previous and previous != doc.name else {}
	frappe.publish_realtime("onechat_labels", payload, room=ROOM, after_commit=True)

	return doc.name


@frappe.whitelist()
def delete_label(name: str):
	guard()
	require(LABEL, "delete")
	ensure_admin()

	frappe.db.delete(CONTACT_LABEL, {"label": name})
	frappe.delete_doc(LABEL, name, ignore_permissions=True)

	frappe.publish_realtime("onechat_labels", {"deleted": name}, room=ROOM, after_commit=True)


def excerpt(text, query, width=60):
	plain = " ".join(strip_html(html.unescape(text or "")).split())
	index = plain.lower().find(query.lower())
	if index < 0:
		return plain[: width * 2]

	start = max(0, index - width)
	end = min(len(plain), index + len(query) + width)
	return ("…" if start else "") + plain[start:end] + ("…" if end < len(plain) else "")


@frappe.whitelist()
def search_thread(contact: str, query: str, limit: int | str = 100):
	guard()
	check_visible(contact)

	query = (query or "").strip()
	if len(query) < 2:
		return []

	limit = min(cint(limit) or 100, 200)
	pattern = f"%{query}%"

	messages = frappe.get_all(
		MESSAGE,
		filters=[
			[MESSAGE, "whatsapp_contact", "=", contact],
			[MESSAGE, "content_type", "!=", "reaction"],
			[MESSAGE, "message", "like", pattern],
		],
		fields=["name", "type", "message", "creation"],
		order_by="creation desc",
		limit_page_length=limit,
	)
	notes = frappe.get_all(
		NOTE,
		filters=[
			[NOTE, "reference_doctype", "=", CONTACT],
			[NOTE, "reference_docname", "=", contact],
			[NOTE, "content", "like", pattern],
		],
		fields=["name", "content", "creation"],
		order_by="creation desc",
		limit_page_length=limit,
	)

	results = [
		{
			"kind": "message",
			"name": row.name,
			"type": row.type,
			"creation": row.creation,
			"snippet": excerpt(row.message, query),
		}
		for row in messages
	] + [
		{
			"kind": "note",
			"name": row.name,
			"type": "Note",
			"creation": row.creation,
			"snippet": excerpt(row.content, query),
		}
		for row in notes
	]
	results.sort(key=lambda row: row["creation"], reverse=True)

	return results[:limit]


def contact_labels(contact):
	return frappe.get_all(
		CONTACT_LABEL,
		filters={"parenttype": CONTACT, "parentfield": "labels", "parent": contact},
		pluck="label",
		order_by="idx asc",
	)


@frappe.whitelist()
def bulk_update(
	contacts: JSON,
	action: str,
	value: JSON = None,
	reason: str | None = None,
	note: str | None = None,
	force: bool | int | str = 0,
):
	guard()
	require(CONTACT, "write")

	if action not in BULK_ACTIONS:
		frappe.throw(_("Unknown action."))
	names = [name for name in dict.fromkeys(frappe.parse_json(contacts) or []) if name][:BULK_LIMIT]
	if not names:
		frappe.throw(_("Pick at least one conversation."))
	for name in names:
		check_visible(name)
	if action in ("add_label", "remove_label") and not value:
		frappe.throw(_("Pick a label."))

	done = 0
	for name in names:
		if not frappe.db.exists(CONTACT, name):
			continue
		if action == "assign":
			assign(name, value or None)
		elif action == "status":
			try:
				set_status(name, value, reason=reason, note=note, force=force)
			except (frappe.ValidationError, frappe.PermissionError):
				frappe.clear_messages()
				continue
		elif action == "read":
			mark_read(name)
		else:
			current = contact_labels(name)
			wanted = (
				[*current, value]
				if action == "add_label" and value not in current
				else [label for label in current if label != value]
			)
			if wanted != current:
				set_labels(name, json.dumps(wanted))
		done += 1

	return done
