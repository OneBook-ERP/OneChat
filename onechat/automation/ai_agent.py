import time
from contextlib import nullcontext

import frappe
from frappe import _
from frappe.utils import cint, nowdate

from onechat.automation.steps import Result, timeout_minutes

SESSION = "OneChat Flow Session"
CONTACT = "OneChat Contact"
MESSAGE = "OneChat Message"
SETTINGS = "OneChat Settings"
DEBOUNCE = 4
TOKEN_TTL = 600
COUNT_TTL = 3 * 86400
DAY_TTL = 2 * 86400
MAX_REPLIES = 20
DAILY_LIMIT = 500
HANDOVER = "handover"
NO_REPLY = "no_reply"


def token_key(session):
	return f"onechat:ai:turn:{session}"


def count_key(session):
	return f"onechat:ai:replies:{session}"


def day_key():
	return f"onechat:ai:day:{nowdate()}"


def waiting(config):
	return Result(wait="Reply", minutes=timeout_minutes(config))


def begin(run, node_id, config):
	if run.simulate:
		return test_reply(run, node_id, config, text_of(run.context.get("message")))
	queue(run, node_id)
	return waiting(config)


def resume(run, node_id, config, event):
	kind = event.get("kind")
	if kind == "timeout":
		return Result(handle=NO_REPLY)
	if kind == "ai":
		reason = event.get("reason") or ""
		run.context.setdefault("ai", {})["handover_reason"] = reason
		return Result(handle=HANDOVER, output={"reason": reason})
	if run.simulate:
		return test_reply(run, node_id, config, text_of(event.get("message")))
	queue(run, node_id)
	return waiting(config)


def text_of(message):
	return ((message or {}).get("text") or "").strip()


def queue(run, node_id):
	if not run.session:
		return
	token = frappe.generate_hash(length=12)
	frappe.cache().set_value(token_key(run.session.name), token, expires_in_sec=TOKEN_TTL)
	frappe.enqueue(
		"onechat.automation.ai_agent.take_turn",
		queue="short",
		session=run.session.name,
		node_id=node_id,
		token=token,
		enqueue_after_commit=True,
	)


def current(session, node_id, token):
	if frappe.cache().get_value(token_key(session), expires=True) != token:
		return False
	row = frappe.db.get_value(SESSION, session, ["status", "current_node"], as_dict=True)
	return bool(row and row.status == "Waiting" and row.current_node == node_id)


def node_config(session_doc, node_id):
	from onechat.automation import engine

	flow = engine.load_flow(session_doc.flow)
	graph = engine.Graph(flow.graph_json or "{}")
	node = graph.nodes.get(node_id)
	return engine.Graph.config(node) if node else {}


def bump(key, ttl):
	value = cint(frappe.cache().get_value(key, expires=True)) + 1
	frappe.cache().set_value(key, value, expires_in_sec=ttl)
	return value


def limit_reason(session, config):
	daily = cint(frappe.get_cached_doc(SETTINGS).get("bot_daily_limit")) or DAILY_LIMIT
	if cint(frappe.cache().get_value(day_key(), expires=True)) >= daily:
		return _("The AI reached today's reply limit.")
	if cint(frappe.cache().get_value(count_key(session), expires=True)) >= (
		cint(config.get("max_replies")) or MAX_REPLIES
	):
		return _("The AI reached its reply limit for this chat.")
	return None


def send(session_doc, text):
	doc = frappe.get_doc(
		{
			"doctype": MESSAGE,
			"type": "Outgoing",
			"message_type": "Manual",
			"source": "Bot",
			"to": session_doc.phone,
			"whatsapp_account": session_doc.whatsapp_account,
			"reference_doctype": CONTACT,
			"reference_name": session_doc.contact,
			"content_type": "text",
			"message": text,
		}
	)
	doc.flags.onechat_flow = True
	doc.insert(ignore_permissions=True)
	return doc.name


def hand_over(session_doc, reason):
	from onechat.automation import engine

	engine.resume(session_doc, {"kind": "ai", "reason": reason})


def load_session(name):
	return frappe.get_doc(SESSION, name)


def take_turn(session, node_id, token):
	time.sleep(DEBOUNCE)
	if not current(session, node_id, token):
		return
	from onechat.automation import run_as

	session_doc = load_session(session)
	with run_as.as_automation_user():
		if not run_as.automation_user():
			return hand_over(session_doc, _("Pick a user under Settings → Automation so the AI can run."))
		config = node_config(session_doc, node_id)
		reason = limit_reason(session, config)
		if reason:
			return hand_over(session_doc, reason)
		reply(session_doc, node_id, token, config)


def reply(session_doc, node_id, token, config):
	from onechat.assistant import bot, llm
	from onechat.assistant.providers import ProviderError
	from onechat.inbox import read_receipts
	from onechat.inbox.conversations import publish_typing

	ctx = bot.Context(session_doc.contact, config, account=session_doc.whatsapp_account)
	publish_typing(session_doc.contact, True, _("AI agent"))
	read_receipts.typing(session_doc.contact)
	try:
		outcome = bot.respond(ctx, bot.history_of(session_doc.contact))
	except (ProviderError, llm.ModelError) as error:
		frappe.log_error(title="OneChat AI agent", message=str(error))
		return hand_over(session_doc, str(error))
	finally:
		publish_typing(session_doc.contact, False)
	if not current(session_doc.name, node_id, token):
		return
	if outcome.text:
		send(session_doc, outcome.text)
		bump(count_key(session_doc.name), COUNT_TTL)
		bump(day_key(), DAY_TTL)
	if outcome.handover:
		hand_over(session_doc, outcome.reason)


def test_reply(run, node_id, config, text):
	from onechat.assistant import bot, llm
	from onechat.assistant.providers import ProviderError

	history = run.state.setdefault("ai", {}).setdefault(node_id, [])
	if text:
		history.append({"role": "user", "content": text})
	from onechat.automation import run_as

	live = bool((run.context.get("test") or {}).get("live")) and bool(run.contact)
	account = frappe.db.get_value(CONTACT, run.contact, "whatsapp_account") if run.contact else None
	ctx = bot.Context(run.contact, config, simulate=not live, account=account, test=True)
	try:
		with run_as.as_automation_user() if live else nullcontext():
			outcome = bot.respond(ctx, bot.merged((row["role"], row["content"]) for row in history))
	except (ProviderError, llm.ModelError) as error:
		run.note(str(error))
		return Result(handle=HANDOVER, output={"reason": str(error)})
	if outcome.text:
		run.send(content_type="text", message=outcome.text)
		history.append({"role": "assistant", "content": outcome.text})
	if outcome.handover:
		run.note(_("Handed over: {0}").format(outcome.reason))
		return Result(handle=HANDOVER, output={"reason": outcome.reason})
	return waiting(config)
