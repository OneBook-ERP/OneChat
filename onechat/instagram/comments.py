import random
import re
from datetime import timedelta

import frappe
import requests
from frappe import _
from frappe.query_builder import Case, Order
from frappe.query_builder.functions import Count, Sum
from frappe.utils import add_days, cint, get_datetime, now_datetime

from onechat.campaigns.chat_links import apply_label
from onechat.inbox import visibility
from onechat.inbox.conversations import CONTACT, MESSAGE, guard, publish, single
from onechat.inbox.visibility import check as check_visible
from onechat.instagram import graph
from onechat.workspace.session import require

SETTINGS = "OneChat Settings"
ACCOUNT = "OneChat Account"
SHOW_ALL = "All comments"
MATCHED = "Matched or replied"
NEVER = "None"
REPLY_DAYS = 7
MEDIA_SECONDS = 300
STATUSES = ("all", "unreplied", "replied", "hidden")
BULK_LIMIT = 100
LINKS = re.compile(r"https?://|www\.", re.I)
DEFAULTS = {
	"ig_comments_in_inbox": "Matched or replied",
	"ig_comment_unread": 1,
	"ig_comment_replies": 0,
	"ig_comment_hide_words": "",
	"ig_comment_hide_links": 0,
	"ig_comment_label": None,
	"ig_comment_hide_negative": 0,
	"ig_comment_negative_level": "Abusive only",
	"ig_story_thanks": 0,
	"ig_story_thanks_message": "",
	"ig_story_thanks_hours": 24,
}


def settings():
	doc = frappe.get_cached_doc(SETTINGS)
	return frappe._dict(
		{
			key: (doc.get(key) if doc.meta.has_field(key) and doc.get(key) is not None else default)
			for key, default in DEFAULTS.items()
		}
	)


def should_hide(text, config):
	text = (text or "").lower()
	if cint(config.ig_comment_hide_links) and LINKS.search(text):
		return True
	words = [
		word.strip().lower() for word in (config.ig_comment_hide_words or "").splitlines() if word.strip()
	]
	return any(word in text for word in words)


def post_link(account, media_id):
	if not media_id:
		return None
	key = f"onechat:instagram-post:{account.name}:{media_id}"
	cache = frappe.cache()
	cached = cache.get_value(key)
	if cached is not None:
		return cached or None
	try:
		link = graph.media(account, media_id).get("permalink") or ""
	except (graph.GraphError, requests.RequestException):
		link = ""
	cache.set_value(key, link, expires_in_sec=86400 if link else 300)
	return link or None


def receive(value, account):
	sender = value.get("from") or {}
	party = str(sender.get("id") or "")
	comment_id = str(value.get("id") or "")
	if not party or not comment_id or party == str(account.ig_user_id or ""):
		return None
	username = (sender.get("username") or "").lower()
	if username and username == (account.get("ig_username") or "").lower():
		return None

	config = settings()
	if value.get("parent_id") and not cint(config.ig_comment_replies):
		return None
	if frappe.db.exists(MESSAGE, {"message_id": comment_id}):
		return None

	doc = frappe.get_doc(
		{
			"doctype": MESSAGE,
			"type": "Incoming",
			"from": party,
			"profile_name": sender.get("username") or party,
			"message_id": comment_id,
			"whatsapp_account": account.name,
			"content_type": "comment",
			"message": value.get("text") or "",
			"media_id": str((value.get("media") or {}).get("id") or ""),
		}
	)
	doc.flags.skip_send = True
	doc.flags.onechat_quiet = config.ig_comments_in_inbox != SHOW_ALL
	doc.flags.onechat_no_unread = not cint(config.ig_comment_unread)
	doc.flags.onechat_skip_flow = True
	doc.insert(ignore_permissions=True)
	frappe.enqueue(
		"onechat.instagram.comments.process",
		queue="short",
		enqueue_after_commit=True,
		message=doc.name,
	)

	contact = doc.get("whatsapp_contact")
	if contact:
		if sender.get("username") and not frappe.db.get_value(CONTACT, contact, "instagram_username"):
			frappe.db.set_value(
				CONTACT,
				contact,
				"instagram_username",
				sender["username"],
				update_modified=False,
			)
		if config.ig_comment_label:
			apply_label(contact, config.ig_comment_label)
	return doc


def process(message):
	from onechat.instagram.sentiment import check

	comment = frappe.get_doc(MESSAGE, message)
	if comment.content_type != "comment":
		return
	if comment.media_id and not comment.link_url:
		link = post_link(graph.account_doc(comment.whatsapp_account), comment.media_id)
		if link:
			frappe.db.set_value(MESSAGE, comment.name, "link_url", link, update_modified=False)
			comment.link_url = link
	if should_hide(comment.message, settings()):
		try:
			hide(comment)
		except (graph.GraphError, requests.RequestException):
			frappe.log_error(
				title="Instagram comment: hide",
				reference_doctype=MESSAGE,
				reference_name=comment.name,
			)
		return
	check(comment)


def show_in_inbox(comment):
	from onechat.inbox.conversations import surface
	from onechat.inbox.routing import route

	config = settings()
	contact = comment.get("whatsapp_contact")
	if config.ig_comments_in_inbox != MATCHED or not contact:
		return
	surface(comment, contact, unread=bool(cint(config.ig_comment_unread)))
	route(comment, contact)


def comment_of(name):
	if not frappe.db.exists(MESSAGE, name):
		frappe.throw(_("That comment no longer exists."), frappe.DoesNotExistError)
	doc = frappe.get_doc(MESSAGE, name)
	if doc.content_type != "comment":
		frappe.throw(_("That message is not an Instagram comment."))
	return doc


def check_private_reply(comment):
	if cint(comment.comment_replied):
		frappe.throw(_("Instagram allows only one private reply per comment."))
	if now_datetime() - get_datetime(comment.creation) > timedelta(days=REPLY_DAYS):
		frappe.throw(_("Private replies are only allowed within {0} days of the comment.").format(REPLY_DAYS))


def authorized(name, permission="create"):
	guard()
	require(MESSAGE, permission)
	comment = comment_of(name)
	check_visible(comment.whatsapp_contact)
	return comment


@frappe.whitelist(methods=["POST"])
def reply_privately(message: str, text: str):
	comment = authorized(message)
	if not (text or "").strip():
		frappe.throw(_("Write a message to send."))
	outgoing = frappe.get_doc(
		{
			"doctype": MESSAGE,
			"type": "Outgoing",
			"whatsapp_account": comment.whatsapp_account,
			"message_type": "Manual",
			"source": "Agent",
			"to": comment.get("from"),
			"message": text,
			"content_type": "text",
			"reference_doctype": CONTACT,
			"reference_name": comment.whatsapp_contact,
			"reply_to_comment": comment.message_id,
		}
	).insert(ignore_permissions=True)
	return single(outgoing.name)


@frappe.whitelist(methods=["POST"])
def reply_publicly(message: str, text: str):
	comment = authorized(message)
	if not (text or "").strip():
		frappe.throw(_("Write a reply."))
	try:
		reply = post_public_reply(comment, text, "Agent")
	except (graph.GraphError, requests.RequestException) as error:
		frappe.throw(str(error), title=_("Instagram"))
	return single(reply.name)


@frappe.whitelist(methods=["POST"])
def set_hidden(message: str, hidden: int | str = 1):
	comment = authorized(message, "write")
	hidden = 1 if cint(hidden) else 0
	try:
		hide(comment, hidden)
	except (graph.GraphError, requests.RequestException) as error:
		frappe.throw(str(error), title=_("Instagram"))
	return {"hidden": hidden}


def post_public_reply(comment, text, source):
	response = graph.reply_to_comment(graph.account_doc(comment.whatsapp_account), comment.message_id, text)
	reply = frappe.get_doc(
		{
			"doctype": MESSAGE,
			"type": "Outgoing",
			"whatsapp_account": comment.whatsapp_account,
			"message_type": "Manual",
			"source": source,
			"to": comment.get("from"),
			"message": text,
			"content_type": "comment_reply",
			"status": "sent",
			"message_id": response.get("id"),
			"reply_to_message_id": comment.message_id,
			"media_id": comment.get("media_id"),
			"link_url": comment.get("link_url"),
			"reference_doctype": CONTACT,
			"reference_name": comment.get("whatsapp_contact"),
		}
	)
	reply.flags.skip_send = True
	reply.flags.onechat_quiet = settings().ig_comments_in_inbox == NEVER
	return reply.insert(ignore_permissions=True)


def hide(comment, hidden=1, auto=False):
	graph.hide_comment(graph.account_doc(comment.whatsapp_account), comment.message_id, bool(hidden))
	frappe.db.set_value(
		MESSAGE,
		comment.name,
		{
			"comment_hidden": 1 if hidden else 0,
			"comment_auto_hidden": 1 if hidden and auto else 0,
		},
		update_modified=False,
	)
	if comment.get("whatsapp_contact"):
		publish(comment.whatsapp_contact, comment.name)


def run_flow_actions(config, comment):
	replies = [
		str(item.get("value") if isinstance(item, dict) else item).strip()
		for item in config.get("public_replies") or []
	]
	replies = [reply for reply in replies if reply]
	try:
		if replies:
			post_public_reply(comment, random.choice(replies), "Bot")
		if cint(config.get("hide_comment")):
			hide(comment)
	except Exception:
		frappe.log_error(
			title="OneChat comment reply",
			reference_doctype=MESSAGE,
			reference_name=comment.name,
		)


@frappe.whitelist()
def recent_posts(account: str | None = None):
	guard()
	from onechat.inbox.accounts import blocked

	allowed = set(frappe.get_all(ACCOUNT, filters={"channel": "Instagram", "status": "Active"}, pluck="name"))
	allowed -= blocked()
	names = [account] if account else sorted(allowed)
	names = [name for name in names if name in allowed]
	posts = [{**row, "account": name} for name in names for row in media_of(name)]
	return sorted(posts, key=lambda row: row.get("timestamp") or "", reverse=True)


def media_of(account):
	key = f"onechat:instagram-media:{account}"
	cache = frappe.cache()
	rows = cache.get_value(key)
	if rows is None:
		try:
			rows = graph.recent_media(graph.account_doc(account))
		except (graph.GraphError, requests.RequestException):
			frappe.log_error(
				title="Instagram recent posts",
				reference_doctype=ACCOUNT,
				reference_name=account,
			)
			return []
		cache.set_value(key, rows, expires_in_sec=MEDIA_SECONDS)
	return rows


def public_replies(table):
	return (
		frappe.qb.from_(table)
		.select(table.reply_to_message_id)
		.where(table.content_type == "comment_reply")
		.where(table.reply_to_message_id.isnotnull())
	)


def replied(message):
	return (message.comment_replied == 1) | message.message_id.isin(
		public_replies(frappe.qb.DocType(MESSAGE).as_("reply"))
	)


def status_condition(message, status):
	return {
		"unreplied": (message.comment_hidden == 0) & ~replied(message),
		"replied": replied(message),
		"hidden": message.comment_hidden == 1,
	}.get(status)


def replied_before(comment, contact):
	message = frappe.qb.DocType(MESSAGE)
	return bool(
		frappe.qb.from_(message)
		.select(message.name)
		.where(
			(message.whatsapp_contact == contact)
			& (message.content_type == "comment")
			& (message.media_id == (comment.get("media_id") or ""))
			& (message.name != comment.name)
			& replied(message)
		)
		.limit(1)
		.run()
	)


def comment_condition(message, contact, account=None, post=None, search=None, days=None):
	condition = message.content_type == "comment"
	scope = visibility.shown(contact)
	if scope is not None:
		condition = condition & scope
	if account:
		condition = condition & (message.whatsapp_account == account)
	if post:
		condition = condition & (message.media_id == post)
	if cint(days):
		condition = condition & (message.creation >= add_days(now_datetime(), -cint(days)))
	if search:
		like = f"%{search.strip()}%"
		condition = condition & (
			message.message.like(like)
			| message.profile_name.like(like)
			| contact.instagram_username.like(like)
			| contact.contact_name.like(like)
		)
	return condition


@frappe.whitelist()
def moderation(
	account: str | None = None,
	post: str | None = None,
	status: str = "all",
	search: str | None = None,
	days: int | str | None = None,
	start: int | str = 0,
	page_length: int | str = 50,
):
	guard()
	require(MESSAGE, "read")
	if status not in STATUSES:
		status = "all"
	message = frappe.qb.DocType(MESSAGE)
	contact = frappe.qb.DocType(CONTACT)
	base = comment_condition(message, contact, account, post, search, days)
	selected = status_condition(message, status)
	page_length = min(max(cint(page_length), 1), 200)
	rows = (
		frappe.qb.from_(message)
		.join(contact)
		.on(contact.name == message.whatsapp_contact)
		.select(
			message.name,
			message.message,
			message.message_id,
			message.media_id,
			message.link_url,
			message.whatsapp_account.as_("account"),
			message.comment_replied,
			message.comment_hidden,
			message.comment_auto_hidden,
			message.creation,
			message.profile_name,
			contact.name.as_("contact"),
			contact.contact_name,
			contact.instagram_username,
			contact.profile_image,
		)
		.where(base if selected is None else base & selected)
		.orderby(message.creation, order=Order.desc)
		.limit(page_length)
		.offset(max(cint(start), 0))
		.run(as_dict=True)
	)
	ids = [row.message_id for row in rows if row.message_id]
	replies = {}
	if ids:
		for reply in frappe.get_all(
			MESSAGE,
			filters={
				"content_type": "comment_reply",
				"reply_to_message_id": ["in", ids],
			},
			fields=["reply_to_message_id", "message", "owner", "creation"],
			order_by="creation asc",
		):
			replies.setdefault(reply.reply_to_message_id, []).append(reply)
	for row in rows:
		row["replies"] = replies.get(row.message_id, [])

	counts = (
		frappe.qb.from_(message)
		.join(contact)
		.on(contact.name == message.whatsapp_contact)
		.select(
			Count(message.name).as_("all"),
			*(
				Sum(Case().when(status_condition(message, key), 1).else_(0)).as_(key)
				for key in STATUSES
				if key != "all"
			),
		)
		.where(base)
		.run(as_dict=True)[0]
	)
	return {
		"comments": rows,
		"totals": {key: cint(counts.get(key)) for key in STATUSES},
		"has_more": len(rows) == page_length,
		"bulk_limit": BULK_LIMIT,
		"reply_days": REPLY_DAYS,
	}


@frappe.whitelist(methods=["POST"])
def hide_many(messages: str | list, hidden: int | str = 1):
	return start_bulk(messages, "hide", hidden=1 if cint(hidden) else 0)


@frappe.whitelist(methods=["POST"])
def reply_many(messages: str | list, mode: str, text: str):
	if mode not in ("private", "public"):
		frappe.throw(_("Choose a private or public reply."))
	if not (text or "").strip():
		frappe.throw(_("Write a message to send."))
	return start_bulk(messages, mode, text=text)


def start_bulk(messages, action, **options):
	guard()
	require(MESSAGE, "write" if action == "hide" else "create")
	names = frappe.parse_json(messages) if isinstance(messages, str) else messages
	names = list(dict.fromkeys(names or []))
	if not names:
		frappe.throw(_("Pick at least one comment."))
	if len(names) > BULK_LIMIT:
		frappe.throw(_("Pick at most {0} comments at a time.").format(BULK_LIMIT))
	job = frappe.generate_hash(length=10)
	frappe.enqueue(
		"onechat.instagram.comments.run_bulk",
		queue="long",
		enqueue_after_commit=True,
		job=job,
		names=names,
		action=action,
		**options,
	)
	return {"job": job, "total": len(names)}


def run_bulk(job, names, action, text=None, hidden=1):
	from onechat.inbox.auto_reply import personalize

	def apply(name):
		if action == "hide":
			return set_hidden(name, hidden)
		contact = frappe.db.get_value(MESSAGE, name, "whatsapp_contact")
		body = personalize(text, contact) if contact else text
		return (reply_privately if action == "private" else reply_publicly)(name, body)

	done = failed = 0
	for name in names:
		frappe.db.savepoint("onechat_comment_bulk")
		try:
			apply(name)
			frappe.db.commit()  # nosemgrep: frappe-manual-commit - commit each processed bulk comment action
			done += 1
		except Exception:
			frappe.db.rollback(save_point="onechat_comment_bulk")
			frappe.clear_last_message()
			failed += 1
		frappe.publish_realtime(
			"onechat_comment_bulk",
			{
				"job": job,
				"done": done,
				"failed": failed,
				"total": len(names),
				"finished": done + failed == len(names),
			},
			user=frappe.session.user,
		)
