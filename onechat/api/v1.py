import frappe
from frappe import _
from frappe.utils import cint

from onechat.api_types import JSON
from onechat.inbox import conversations
from onechat.inbox.conversations import CONTACT, MESSAGE, find_contact, find_instagram_contact, guard
from onechat.inbox.visibility import check as check_visible

CONTACT_FIELDS = [
	"name",
	"contact_name",
	"mobile_no",
	"email",
	"assigned_to",
	"conversation_status",
	"reference_doctype",
	"reference_docname",
	"channel",
	"instagram_username",
]


def contact_data(row, labels=None):
	if not row:
		return None
	return {
		"id": row.get("name"),
		"name": row.get("contact_name"),
		"channel": row.get("channel") or "WhatsApp",
		"phone": row.get("mobile_no"),
		"instagram_username": row.get("instagram_username"),
		"email": row.get("email"),
		"assigned_to": row.get("assigned_to"),
		"status": row.get("conversation_status"),
		"labels": labels or [],
		"linked_doctype": row.get("reference_doctype"),
		"linked_name": row.get("reference_docname"),
	}


def message_data(message):
	return {
		"id": message.get("name"),
		"direction": "incoming" if message.get("type") == "Incoming" else "outgoing",
		"channel": message.get("channel") or "WhatsApp",
		"type": message.get("content_type"),
		"text": message.get("message"),
		"template": message.get("template"),
		"status": message.get("status"),
		"source": message.get("source"),
		"created_at": str(message.get("creation")) if message.get("creation") else None,
	}


def contact_for(phone, name=None, create=False):
	if not conversations.digits(phone):
		frappe.throw(_("Pass a phone number with the country code."))
	contact = find_contact(phone)
	if contact or not create:
		return contact
	return (
		frappe.get_doc({"doctype": CONTACT, "contact_name": name or phone, "mobile_no": phone})
		.insert(ignore_permissions=True)
		.name
	)


def resolve(ref, name=None, create=False):
	ref = str(ref or "").strip()
	if not ref:
		frappe.throw(_("Pass a phone number, an @username, ig:<Instagram ID> or a contact ID."))
	if frappe.db.exists(CONTACT, ref):
		return ref
	if ref.startswith("@"):
		return frappe.db.get_value(CONTACT, {"channel": "Instagram", "instagram_username": ref[1:]})
	if ref.lower().startswith("ig:"):
		return find_instagram_contact(ref[3:])
	return contact_for(ref, name, create)


def missing(ref):
	frappe.throw(_("No contact matches {0}.").format(ref), frappe.DoesNotExistError)


def described(contact):
	row = frappe.db.get_value(CONTACT, contact, CONTACT_FIELDS, as_dict=True)
	return contact_data(row, conversations.contact_labels(contact))


@frappe.whitelist(methods=["POST"])
def send_message(to: str | int, text: str, name: str | None = None):
	guard()
	contact = resolve(to, name, create=True) or missing(to)
	message = conversations.send(contact, message=text)
	return {"contact": described(contact), "message": message_data(message)}


@frappe.whitelist(methods=["POST"])
def send_template(to: str | int, template: str, parameters: JSON = None, name: str | None = None):
	guard()
	contact = resolve(to, name, create=True) or missing(to)
	values = frappe.parse_json(parameters) if isinstance(parameters, str) else parameters
	message = conversations.send_template(contact, template, frappe.as_json(values or []))
	return {"contact": described(contact), "message": message_data(message)}


@frappe.whitelist()
def get_contact(phone: str | int):
	guard()
	contact = resolve(phone) or missing(phone)
	check_visible(contact)
	return described(contact)


@frappe.whitelist()
def get_messages(phone: str | int, limit: int | str = 20):
	guard()
	contact = resolve(phone) or missing(phone)
	check_visible(contact)
	rows = frappe.get_all(
		MESSAGE,
		filters={"whatsapp_contact": contact},
		fields=[
			"name",
			"type",
			"channel",
			"content_type",
			"message",
			"template",
			"status",
			"source",
			"creation",
		],
		order_by="creation desc",
		limit_page_length=min(cint(limit) or 20, 100),
	)
	return {"contact": described(contact), "messages": [message_data(row) for row in rows]}


def require(phone):
	contact = resolve(phone) or missing(phone)
	check_visible(contact)
	return contact


def as_list(value):
	value = frappe.parse_json(value) if isinstance(value, str) and value.strip().startswith("[") else value
	if isinstance(value, str):
		value = [part.strip() for part in value.split(",")]
	return [item for item in value or [] if item]


@frappe.whitelist()
def list_conversations(
	status: str | None = None,
	assigned_to: str | None = None,
	label: str | None = None,
	unread: bool | int | str = 0,
	search: str | None = None,
	start: int | str = 0,
	limit: int | str = 20,
	channel: str | None = None,
):
	guard()
	filters = {"disable": 0}
	if channel:
		filters["channel"] = "Instagram" if str(channel).lower() == "instagram" else "WhatsApp"
	if status:
		filters["conversation_status"] = str(status).capitalize()
	if assigned_to:
		filters["assigned_to"] = (
			frappe.session.user if assigned_to == "me" else (None if assigned_to == "none" else assigned_to)
		)
	if cint(unread):
		filters["unread_count"] = [">", 0]
	if label:
		filters["name"] = [
			"in",
			frappe.get_all(
				"OneChat Contact Label", filters={"parenttype": CONTACT, "label": label}, pluck="parent"
			)
			or [""],
		]
	or_filters = None
	if search:
		pattern = f"%{search}%"
		or_filters = {
			"contact_name": ["like", pattern],
			"mobile_no": ["like", pattern],
			"email": ["like", pattern],
			"instagram_username": ["like", pattern],
		}
	rows = frappe.get_list(
		CONTACT,
		filters=filters,
		or_filters=or_filters,
		fields=[*CONTACT_FIELDS, "unread_count", "last_message", "last_message_at"],
		order_by="last_message_at desc",
		limit_start=cint(start),
		limit_page_length=min(cint(limit) or 20, 100),
	)
	labels = conversations.label_map([row.name for row in rows])
	return [
		{
			**contact_data(row, labels.get(row.name, [])),
			"unread": cint(row.unread_count),
			"last_message": row.last_message,
			"last_message_at": str(row.last_message_at) if row.last_message_at else None,
		}
		for row in rows
	]


@frappe.whitelist(methods=["POST"])
def create_contact(phone: str | int, name: str | None = None, email: str | None = None, labels: JSON = None):
	guard()
	if contact_for(phone):
		frappe.throw(_("A contact with that number already exists."), frappe.DuplicateEntryError)
	contact = (
		frappe.get_doc(
			{"doctype": CONTACT, "contact_name": name or phone, "mobile_no": phone, "email": email}
		)
		.insert(ignore_permissions=True)
		.name
	)
	if labels:
		conversations.set_labels(contact, frappe.as_json(as_list(labels)))
	return described(contact)


@frappe.whitelist(methods=["POST"])
def update_contact(phone: str | int, name: str | None = None, email: str | None = None):
	guard()
	contact = require(phone)
	values = {key: value for key, value in (("contact_name", name), ("email", email)) if value is not None}
	if values:
		frappe.db.set_value(CONTACT, contact, values)
		conversations.publish(contact)
	return described(contact)


@frappe.whitelist(methods=["POST"])
def send_media(
	to: str | int, url: str, type: str = "image", caption: str | None = None, name: str | None = None
):
	guard()
	if type not in ("image", "video", "audio", "document"):
		frappe.throw(_("Type must be image, video, audio or document."))
	contact = resolve(to, name, create=True) or missing(to)
	message = conversations.send(contact, message=caption or "", attach=url, content_type=type)
	return {"contact": described(contact), "message": message_data(message)}


@frappe.whitelist(methods=["POST"])
def assign(phone: str | int, user: str | None = None, team: str | None = None):
	guard()
	contact = require(phone)
	if not user and team:
		from onechat.inbox.routing import config, mark_assigned, next_agent

		agent = next_agent(config(), team, contact)
		if not agent:
			frappe.throw(_("Nobody in {0} can take the chat right now.").format(team))
		mark_assigned(agent)
		user = agent.user
	conversations.assign(contact, user or None)
	return described(contact)


@frappe.whitelist(methods=["POST"])
def set_status(phone: str | int, status: str, reason: str | None = None, note: str | None = None):
	guard()
	contact = require(phone)
	conversations.set_status(contact, str(status).lower(), reason=reason, note=note, force=1)
	return described(contact)


@frappe.whitelist(methods=["POST"])
def add_labels(phone: str | int, labels: JSON):
	guard()
	contact = require(phone)
	current = conversations.contact_labels(contact)
	conversations.set_labels(
		contact, frappe.as_json(current + [label for label in as_list(labels) if label not in current])
	)
	return described(contact)


@frappe.whitelist(methods=["POST"])
def remove_labels(phone: str | int, labels: JSON):
	guard()
	contact = require(phone)
	drop = set(as_list(labels))
	conversations.set_labels(
		contact,
		frappe.as_json([label for label in conversations.contact_labels(contact) if label not in drop]),
	)
	return described(contact)


@frappe.whitelist(methods=["POST"])
def add_note(phone: str | int, text: str):
	guard()
	contact = require(phone)
	note = conversations.save_note(contact=contact, content=text)
	return {"contact": contact, "note": {"id": note.get("name"), "text": text}}


@frappe.whitelist(methods=["POST"])
def set_opt_out(phone: str | int, opted_out: int | str = 1):
	guard()
	from onechat.inbox.consent import set_opted_out

	contact = require(phone)
	set_opted_out(contact, 1 if cint(opted_out) else 0)
	return described(contact)


@frappe.whitelist()
def list_templates(status: str = "APPROVED"):
	guard()
	filters = {"status": status} if status else {}
	return [
		{
			"name": row.name,
			"template": row.template_name,
			"language": row.language_code,
			"category": row.category,
			"status": row.status,
			"body": row.template,
			"variables": [
				part.strip()
				for part in (row.field_names or row.sample_values or "").split(",")
				if part.strip()
			],
		}
		for row in frappe.get_list(
			"WhatsApp Templates",
			filters=filters,
			fields=[
				"name",
				"template_name",
				"language_code",
				"category",
				"status",
				"template",
				"field_names",
				"sample_values",
			],
			order_by="template_name asc",
			limit_page_length=0,
		)
	]


@frappe.whitelist(methods=["POST"])
def start_flow(phone: str | int, flow: str, variables: JSON = None):
	guard()
	from onechat.automation import engine

	contact = resolve(phone, create=True) or missing(phone)
	check_visible(contact)
	values = frappe.parse_json(variables) if isinstance(variables, str) else variables
	session = engine.start(flow, {"trigger": "api", "vars": values or {}}, contact=contact)
	return {"contact": contact, "flow": flow, "status": session.status, "run": session.execution_log}
