import json
import re

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, now_datetime, strip_html

from onechat.api_types import JSON
from onechat.assistant import fac
from onechat.assistant.providers import (
	CLAUDE,
	CLAUDE_MODEL,
	OPENAI,
	OPENAI_MODEL,
	OTHER,
	ProviderError,
	build,
	token_limit,
)
from onechat.inbox.visibility import check as check_visible
from onechat.integrations import links
from onechat.workspace.session import can, require_admin, require_app_user

SETTINGS = "OneChat Settings"
CONTACT = "OneChat Contact"
MESSAGE = "OneChat Message"
MAX_STEPS = 8
SESSION_TTL = 3600
HISTORY = 12
DRAFT = re.compile(r"<draft>(.*?)</draft>", re.S)

SYSTEM = """You are the assistant inside OneChat, a WhatsApp inbox used by a business's sales and support agents. \
The agent is looking at one customer's WhatsApp chat. Help them with that customer using the tools, which read and \
change records in the business's ERPNext and CRM with the agent's own permissions.

Look records up instead of guessing. Never invent amounts, dates, order numbers or statuses. If a tool fails or \
finds nothing, say so plainly. Keep answers short and practical, with amounts and dates as they appear in the records.

Write like a helpful colleague in a chat: plain, natural sentences. Never use Markdown, so no asterisks, bold, \
headings, tables, code blocks or bullet symbols. When you list several records, start with one short sentence, then \
put each record on its own line in the form "SAL-ORD-2026-00019, To Pay, 3,926.00", and end with a short takeaway \
if it helps.

When the agent asks you to draft or write a reply to the customer, write the message the agent can send, inside \
<draft></draft> tags, in plain WhatsApp style: short, friendly, no markdown headings. Put any notes for the agent \
outside the tags.

When the agent asks you to message, send, reply to or tell the customer something, call the send_message tool with \
the exact text. It goes out from the business's account in this chat after the agent confirms. Never create \
OneChat Message, WhatsApp Message or any other message records with the document tools.

Only create, update or submit records when the agent clearly asks for it. Those actions wait for the agent to confirm."""

GLOBAL = """You are the assistant inside OneChat, the WhatsApp workspace a business uses next to its ERPNext and CRM. \
The user can open you from any page. Each question comes with the page they are on, and the customer they have open \
if there is one. Use the tools, which read and change records in ERPNext, CRM and OneChat with the user's own \
permissions, to answer questions about customers, orders, invoices, stock, leads, deals and conversations, to compare \
and total figures, and to carry out tasks they ask for.

Look records up instead of guessing. Never invent amounts, dates, names or statuses. If a tool fails or finds \
nothing, say so plainly. If a question is unclear, ask one short follow-up question.

Write like a helpful colleague in a chat: plain, natural sentences. Never use Markdown, so no asterisks, bold, \
headings, tables, code blocks or bullet symbols. When you list several records, start with one short sentence, then \
put each record on its own line in the form "SAL-ORD-2026-00019, To Pay, 3,926.00", and end with a short takeaway \
if it helps. Suggest a sensible next step when there is one.

When the user asks you to draft a WhatsApp message, write it inside <draft></draft> tags in plain WhatsApp style: \
short and friendly. Put any notes for the user outside the tags.

You can only send messages from inside a customer's chat. If the user asks you to message someone, write the \
message as a draft and tell them to open that customer's chat to send it. Never create OneChat Message, WhatsApp \
Message or any other message records with the document tools.

Only create, update or submit records when the user clearly asks for it. Those actions wait for the user to confirm."""
PAGE_TEXT = 300
CHAT = "OneChat Assistant Chat"
GLOBAL_SCOPE = "global"
KEEP_TURNS = 10
RECALL_TURNS = 4
RECALL_TEXT = 500
KEEP_DAYS = 30
CARD_FIELDS = 8
CARD_LINES = 20
ROW_KEYS = ("item_code", "item_name", "item", "description", "account", "employee", "label")
SEND_TOOL = "send_message"
SEND_SPEC = {
	"name": SEND_TOOL,
	"description": "Send a message to the customer whose chat is open, from the business's WhatsApp or Instagram "
	"account. Use it whenever the agent asks you to message, reply to or tell the customer something. "
	"The agent confirms before it is sent.",
	"schema": {
		"type": "object",
		"properties": {
			"text": {"type": "string", "description": "The exact message to send, in plain chat style."}
		},
		"required": ["text"],
	},
}
KINDS = {
	"create_document": "create",
	"update_document": "update",
	"submit_document": "submit",
	"run_workflow": "workflow",
}


def settings():
	return frappe.get_cached_doc(SETTINGS)


@frappe.whitelist()
def status():
	require_app_user()
	config = settings()
	level = fac.access() if cint(config.get("assistant_enabled")) else None
	sign_ins = fac.sign_ins(frappe.session.user) if level else []
	usable = fac.installed()
	return {
		"enabled": bool(cint(config.get("assistant_enabled"))),
		"installed": usable or bool(sign_ins),
		"provider": provider_label(config),
		"access": sorted(level) if level else None,
		"sign_ins": sign_ins,
		"ready": bool(level) and (usable or bool(sign_ins)) and bool(key_of(config)),
		"usable": usable,
	}


KEY_FIELDS = {OPENAI: "assistant_openai_key", OTHER: "assistant_other_key", CLAUDE: "assistant_anthropic_key"}


def key_of(config):
	field = KEY_FIELDS.get(config.get("assistant_provider") or CLAUDE, "assistant_anthropic_key")
	return config.get_password(field, raise_exception=False)


def provider_label(config):
	if config.get("assistant_provider") == OTHER:
		return (config.get("assistant_other_name") or "").strip() or OTHER
	return config.get("assistant_provider") or CLAUDE


def cache_key(name):
	return f"onechat:assistant:session:{name}"


def load(name):
	data = frappe.cache().get_value(cache_key(name)) if name else None
	if not data or data.get("user") != frappe.session.user:
		return None
	return data


def store(data):
	frappe.cache().set_value(cache_key(data["name"]), data, expires_in_sec=SESSION_TTL)


def context(contact):
	row = (
		frappe.db.get_value(
			CONTACT,
			contact,
			["contact_name", "mobile_no", "reference_doctype", "reference_docname", "conversation_status"],
			as_dict=True,
		)
		or {}
	)
	lines = [
		f"Customer: {row.get('contact_name') or '-'}",
		f"WhatsApp number: {row.get('mobile_no') or '-'}",
		f"Chat status: {row.get('conversation_status') or 'Open'}",
	]
	for link in links.of(contact):
		lines.append(f"Linked record: {link.doctype} {link.name}")
	recent = frappe.get_all(
		MESSAGE,
		filters={"whatsapp_contact": contact, "content_type": ["!=", "reaction"]},
		fields=["type", "message", "content_type", "creation"],
		order_by="creation desc",
		limit_page_length=HISTORY,
	)
	if recent:
		lines.append("\nRecent chat (oldest first):")
		for message in reversed(recent):
			who = "Customer" if message.type == "Incoming" else "Business"
			text = strip_html(message.message or "").strip() or f"[{message.content_type}]"
			lines.append(f"- {who}: {text[:300]}")
	return "\n".join(lines)


def page_context(page):
	page = frappe.parse_json(page) if page else {}
	if not isinstance(page, dict):
		return ""
	lines = [f"Page: {str(page.get('title') or page.get('route') or 'OneChat')[:PAGE_TEXT]}"]
	if page.get("path"):
		lines.append(f"Address: {str(page['path'])[:PAGE_TEXT]}")
	for key, value in (page.get("params") or {}).items():
		if value and isinstance(value, str) and key != "contact":
			lines.append(f"{str(key)[:40]}: {value[:PAGE_TEXT]}")
	contact = page.get("contact")
	if contact and isinstance(contact, str) and frappe.db.exists(CONTACT, contact):
		try:
			check_visible(contact)
		except frappe.PermissionError:
			return "\n".join(lines)
		lines.append("\nCustomer open on this page:\n" + context(contact))
	return "\n".join(lines)


def engine(data):
	config = settings()
	level = fac.access()
	if not level:
		frappe.throw(_("You don't have access to the assistant."), frappe.PermissionError)
	tools = fac.tools(frappe.session.user, level)
	if data.get("contact") and can("OneChat Message", "create"):
		tools = [*tools, SEND_SPEC]
	return build(config, SYSTEM if data.get("contact") else GLOBAL, tools), level


def reply(data, text, refused=False):
	drafts = [match.strip() for match in DRAFT.findall(text or "")]
	clean = DRAFT.sub("", text or "").strip()
	return {
		"session": data["name"],
		"reply": _("The assistant can't help with that request.") if refused else clean,
		"draft": drafts[-1] if drafts else "",
		"pending": None,
		"steps": data.get("steps", [])[data.get("mark", 0) :],
	}


def send_to_customer(data, arguments):
	from onechat.inbox.conversations import send

	text = (arguments.get("text") or "").strip()
	if not data.get("contact"):
		return _("No customer chat is open, so nothing was sent."), True
	if not text:
		return _("There was no message to send."), True
	try:
		send(data["contact"], message=text)
	except frappe.ValidationError as error:
		frappe.clear_last_message()
		return _("The message was not sent: {0}").format(strip_html(str(error))), True
	return _("Sent to the customer: {0}").format(text), False


def execute(data, call, level):
	if call["name"] == SEND_TOOL:
		text, error = send_to_customer(data, call.get("input") or {})
	else:
		text, error = fac.call(frappe.session.user, call["name"], call["input"], level)
	data.setdefault("steps", []).append({"tool": call["name"], "ok": not error})
	return {"id": call["id"], "text": text, "error": error}


def run(data, provider, level):
	for step in range(MAX_STEPS):
		turn = provider.step(data["messages"])
		if turn.refused:
			store(data)
			return reply(data, "", refused=True)
		if not turn.calls:
			store(data)
			return reply(data, turn.text)

		done, pending = [], []
		for call in turn.calls:
			if call["name"] == SEND_TOOL:
				pending.append(call)
			elif not fac.allowed(call["name"], level):
				done.append(
					{"id": call["id"], "text": _("This tool is not available to you."), "error": True}
				)
			elif fac.needs_confirm(call["name"]):
				pending.append(call)
			else:
				done.append(execute(data, call, level))

		if pending:
			data["pending"] = {"calls": pending, "done": done, "order": [call["id"] for call in turn.calls]}
			store(data)
			return {
				**reply(data, turn.text),
				"pending": [
					{"tool": call["name"], "input": call["input"], "card": card(call)} for call in pending
				],
			}

		provider.results(data["messages"], done)

	store(data)
	return reply(data, _("That took too many steps. Try asking in a simpler way."))


@frappe.whitelist(methods=["POST"])
def ask(
	contact: str | None = None, question: str | None = None, session: str | None = None, page: JSON = None
):
	require_app_user()
	contact = contact or None
	if contact:
		check_visible(contact)
	question = (question or "").strip()
	if not question:
		frappe.throw(_("Type a question for the assistant."))

	data = load(session)
	fresh = not data or data.get("contact") != contact or data.get("pending")
	if fresh:
		data = {
			"name": frappe.generate_hash(length=16),
			"user": frappe.session.user,
			"contact": contact,
			"messages": [],
			"steps": [],
		}
	earlier = recall(contact) if fresh else ""
	if contact:
		text = (
			"\n\n".join(part for part in (context(contact), earlier, f"Agent's question: {question}") if part)
			if fresh
			else question
		)
	else:
		where = page_context(page)
		text = "\n\n".join(part for part in (where, earlier, f"Question: {question}") if part)

	data["mark"] = len(data.get("steps", []))
	try:
		provider, level = engine(data)
		provider.ask(data["messages"], text)
		result = run(data, provider, level)
	except (ProviderError, fac.FacError) as error:
		frappe.throw(str(error))
	remember(contact, question, result)
	return result


@frappe.whitelist(methods=["POST"])
def confirm(session: str, approve: bool | int | str = 0):
	require_app_user()
	data = load(session)
	if not data or not data.get("pending"):
		frappe.throw(_("This request has expired. Ask again."))
	if data.get("contact"):
		check_visible(data["contact"])
	data["mark"] = len(data.get("steps", []))

	try:
		provider, level = engine(data)
		pending = data.pop("pending")
		results = {row["id"]: row for row in pending["done"]}
		for call in pending["calls"]:
			if cint(approve):
				results[call["id"]] = execute(data, call, level)
			else:
				results[call["id"]] = {
					"id": call["id"],
					"text": _("The agent cancelled this action."),
					"error": True,
				}
		provider.results(data["messages"], [results[name] for name in pending["order"] if name in results])
		result = run(data, provider, level)
	except (ProviderError, fac.FacError) as error:
		frappe.throw(str(error))
	remember_more(data.get("contact"), result)
	return result


def scope_of(contact):
	return contact or GLOBAL_SCOPE


def memory(contact):
	return frappe.db.get_value(
		CHAT,
		{"user": frappe.session.user, "scope": scope_of(contact)},
		["name", "turns", "session"],
		as_dict=True,
	)


def stored_turns(row):
	value = row.turns if row else None
	if isinstance(value, str):
		try:
			value = json.loads(value)
		except ValueError:
			value = None
	return value if isinstance(value, list) else []


def save_turns(contact, turns, session):
	turns = turns[-KEEP_TURNS:]
	values = {"turns": json.dumps(turns, default=str), "session": session, "turn_count": len(turns)}
	row = memory(contact)
	if row:
		frappe.db.set_value(CHAT, row.name, values)
		return
	frappe.get_doc(
		{
			"doctype": CHAT,
			"user": frappe.session.user,
			"scope": scope_of(contact),
			"contact": contact,
			**values,
		}
	).insert(ignore_permissions=True)


def remember(contact, question, result):
	try:
		turns = stored_turns(memory(contact))
		turns.append(
			{
				"question": question,
				"reply": result.get("reply") or "",
				"draft": result.get("draft") or "",
				"steps": result.get("steps") or [],
				"pending": result.get("pending"),
				"at": str(now_datetime()),
			}
		)
		save_turns(contact, turns, result.get("session"))
	except Exception:
		frappe.log_error(title="OneChat assistant history")


def remember_more(contact, result):
	try:
		turns = stored_turns(memory(contact))
		if not turns:
			return
		last = turns[-1]
		last["reply"] = "\n\n".join(part for part in (last.get("reply"), result.get("reply")) if part)
		last["draft"] = result.get("draft") or last.get("draft") or ""
		last["steps"] = (last.get("steps") or []) + (result.get("steps") or [])
		last["pending"] = result.get("pending")
		save_turns(contact, turns, result.get("session"))
	except Exception:
		frappe.log_error(title="OneChat assistant history")


def recall(contact):
	turns = [turn for turn in stored_turns(memory(contact)) if turn.get("question")][-RECALL_TURNS:]
	if not turns:
		return ""
	lines = ["Earlier conversation with you here (oldest first, for context only):"]
	for turn in turns:
		lines.append(f"- Asked: {turn['question'][:RECALL_TEXT]}")
		answer = (turn.get("reply") or turn.get("draft") or "").strip()
		if answer:
			lines.append(f"  You said: {answer[:RECALL_TEXT]}")
	return "\n".join(lines)


@frappe.whitelist()
def history(contact: str | None = None):
	require_app_user()
	contact = contact or None
	if contact:
		check_visible(contact)
	row = memory(contact)
	turns = stored_turns(row)
	data = load(row.session) if row and row.session else None
	live = bool(data) and data.get("contact") == contact
	if turns and turns[-1].get("pending") and not (live and data.get("pending")):
		turns[-1]["pending"] = None
	return {"turns": turns, "session": row.session if live else None}


@frappe.whitelist(methods=["POST"])
def forget(contact: str | None = None):
	require_app_user()
	row = memory(contact or None)
	if row:
		frappe.delete_doc(CHAT, row.name, ignore_permissions=True)


def cleanup_history():
	frappe.db.delete(CHAT, {"modified": ["<", add_days(now_datetime(), -KEEP_DAYS)]})


def field_label(doctype, fieldname):
	try:
		label = frappe.get_meta(doctype).get_label(fieldname) if doctype else None
	except Exception:
		label = None
	return label if label and label != "No Label" else fieldname.replace("_", " ").capitalize()


def tool_values(arguments):
	values = (
		next((arguments.get(key) for key in ("data", "values", "doc", "fields") if arguments.get(key)), None)
		or {}
	)
	if isinstance(values, str):
		try:
			values = json.loads(values)
		except ValueError:
			values = {}
	return values if isinstance(values, dict) else {}


def card_lines(rows):
	lines, total, priced = [], 0.0, False
	for row in rows[:CARD_LINES]:
		qty = flt(row.get("qty") or row.get("quantity")) or None
		rate = row.get("rate") if row.get("rate") is not None else row.get("price")
		amount = flt(row.get("amount")) or (flt(qty or 1) * flt(rate) if rate is not None else None)
		if amount:
			total += amount
			priced = True
		lines.append(
			{
				"item": next((str(row[key]) for key in ROW_KEYS if row.get(key)), _("Row")),
				"qty": qty,
				"rate": flt(rate) if rate is not None else None,
				"amount": amount,
			}
		)
	return lines, round(total, 2) if priced else None


def send_card(call):
	return {
		"kind": "send",
		"title": _("Send this message to the customer?"),
		"doctype": "",
		"name": "",
		"fields": [{"label": _("Message"), "value": str((call.get("input") or {}).get("text") or "")[:1000]}],
		"more_fields": 0,
		"lines": [],
		"more_lines": 0,
		"total": None,
		"warning": None,
	}


def card(call):
	if call["name"] == SEND_TOOL:
		return send_card(call)
	name = fac.base(call["name"])
	arguments = call.get("input") or {}
	doctype = arguments.get("doctype") or ""
	docname = arguments.get("name") or arguments.get("docname") or arguments.get("document_name") or ""
	values = tool_values(arguments)
	scalars = [
		(key, value)
		for key, value in values.items()
		if key not in ("doctype", "name") and value not in (None, "") and not isinstance(value, list | dict)
	]
	table = next(
		(
			value
			for value in values.values()
			if isinstance(value, list) and value and all(isinstance(row, dict) for row in value)
		),
		[],
	)
	lines, total = card_lines(table)
	kind = KINDS.get(name, "other")
	what = _(doctype) if doctype else _("record")
	if kind == "create" and len(table) > 1:
		title = _("Create {0} for {1} items?").format(what, len(table))
	elif kind == "create" and table:
		title = _("Create {0} for 1 item?").format(what)
	elif kind == "create":
		title = _("Create {0}?").format(what)
	elif kind == "update":
		title = _("Update {0} {1}?").format(what, docname)
	elif kind == "submit":
		title = _("Submit {0} {1}?").format(what, docname)
	elif kind == "workflow":
		title = _("{0} on {1} {2}?").format(arguments.get("action") or _("Run workflow"), what, docname)
	else:
		title = _("{0}?").format(name.replace("_", " ").capitalize())
	return {
		"kind": kind,
		"title": " ".join(title.split()),
		"doctype": doctype,
		"name": docname,
		"fields": [
			{"label": field_label(doctype, key), "value": str(value)[:200]}
			for key, value in scalars[:CARD_FIELDS]
		],
		"more_fields": max(0, len(scalars) - CARD_FIELDS),
		"lines": lines,
		"more_lines": max(0, len(table) - CARD_LINES),
		"total": total,
		"warning": _("This can't be undone here. To reverse it, cancel the document in ERPNext.")
		if kind in ("submit", "workflow")
		else None,
	}


@frappe.whitelist()
def get_settings():
	require_admin()
	config = settings()
	return {
		"enabled": bool(cint(config.get("assistant_enabled"))),
		"provider": config.get("assistant_provider") or CLAUDE,
		"openai_model": config.get("assistant_openai_model") or "",
		"claude_model": config.get("assistant_claude_model") or "",
		"max_tokens": token_limit(config.get("assistant_max_tokens")),
		"agent_signin": fac.per_agent(),
		"defaults": {"claude_model": CLAUDE_MODEL, "openai_model": OPENAI_MODEL},
		"has_anthropic_key": bool(config.get_password("assistant_anthropic_key", raise_exception=False)),
		"has_openai_key": bool(config.get_password("assistant_openai_key", raise_exception=False)),
		"other_name": config.get("assistant_other_name") or "",
		"other_url": config.get("assistant_other_url") or "",
		"other_model": config.get("assistant_other_model") or "",
		"has_other_key": bool(config.get_password("assistant_other_key", raise_exception=False)),
		"roles": [
			{
				"role": row.role,
				"read": bool(cint(row.get("can_read"))) if row.get("can_read") is not None else True,
				"write": bool(cint(row.get("can_write")))
				if row.get("can_write") is not None
				else row.access == fac.READ_WRITE,
				"create": bool(cint(row.get("can_create")))
				if row.get("can_create") is not None
				else row.access == fac.READ_WRITE,
			}
			for row in config.get("assistant_roles") or []
		],
		"sites": ([frappe.local.site] if fac.local_installed() else [])
		+ [row.label for row in fac.fac_sites()],
	}


@frappe.whitelist(methods=["POST"])
def save_settings(
	enabled: bool | int | str = 0,
	provider: str = CLAUDE,
	openai_model: str | None = None,
	claude_model: str | None = None,
	max_tokens: int | str | None = None,
	anthropic_key: str | None = None,
	openai_key: str | None = None,
	roles: JSON = None,
	agent_signin: bool | int | str = 1,
	other_name: str | None = None,
	other_url: str | None = None,
	other_model: str | None = None,
	other_key: str | None = None,
):
	require_admin()
	if provider not in (CLAUDE, OPENAI, OTHER):
		frappe.throw(_("Choose Claude, OpenAI or another provider."))
	doc = frappe.get_doc(SETTINGS)
	doc.assistant_enabled = cint(enabled)
	doc.assistant_provider = provider
	doc.assistant_openai_model = (openai_model or "").strip() or None
	doc.assistant_claude_model = (claude_model or "").strip() or None
	doc.assistant_max_tokens = token_limit(max_tokens)
	if doc.meta.has_field("assistant_agent_signin"):
		doc.assistant_agent_signin = cint(agent_signin)
	if anthropic_key:
		doc.assistant_anthropic_key = anthropic_key.strip()
	if openai_key:
		doc.assistant_openai_key = openai_key.strip()
	if doc.meta.has_field("assistant_other_url"):
		doc.assistant_other_name = (other_name or "").strip() or None
		doc.assistant_other_url = (other_url or "").strip() or None
		doc.assistant_other_model = (other_model or "").strip() or None
		if other_key:
			doc.assistant_other_key = other_key.strip()
	rows = frappe.parse_json(roles) if roles else []
	doc.set(
		"assistant_roles",
		[
			{
				"role": row.get("role"),
				"can_read": 1 if (row.get("read") or row.get("write") or row.get("create")) else 0,
				"can_write": cint(row.get("write")),
				"can_create": cint(row.get("create")),
				"access": fac.READ_WRITE if (row.get("write") or row.get("create")) else fac.READ_ONLY,
			}
			for row in rows
			if row.get("role")
		],
	)
	doc.save(ignore_permissions=True)
	return get_settings()
