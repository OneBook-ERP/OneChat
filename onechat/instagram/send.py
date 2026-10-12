import json
from datetime import timedelta

import frappe
import requests
from frappe import _
from frappe.utils import get_datetime, get_url, now_datetime, strip_html

from onechat.inbox.conversations import CONTACT, MESSAGE, find_instagram_contact
from onechat.instagram import graph, media

WINDOW_HOURS = 24
HUMAN_AGENT_DAYS = 7
TEXT_LIMIT = 1000
QUICK_REPLY_LIMIT = 13
ATTACHMENT = {"image": "image", "video": "video", "audio": "audio", "document": "file"}


def contact_of(doc):
	if doc.get("whatsapp_contact"):
		return doc.whatsapp_contact
	if doc.reference_doctype == CONTACT and doc.reference_name:
		return doc.reference_name
	return find_instagram_contact(doc.to, doc.whatsapp_account)


def last_incoming(contact):
	return frappe.db.get_value(
		MESSAGE,
		{
			"whatsapp_contact": contact,
			"type": "Incoming",
			"content_type": ["not in", ["comment", "reaction"]],
		},
		"creation",
		order_by="creation desc",
	)


def rules(doc, contact):
	last = last_incoming(contact) if contact else None
	if not last:
		frappe.throw(_("Instagram only allows replies. This person hasn't messaged your account yet."))
	age = now_datetime() - get_datetime(last)
	if age <= timedelta(hours=WINDOW_HOURS):
		return {"messaging_type": "RESPONSE"}
	if doc.source == "Agent" and age <= timedelta(days=HUMAN_AGENT_DAYS):
		return {"messaging_type": "MESSAGE_TAG", "tag": "HUMAN_AGENT"}
	frappe.throw(
		_(
			"The Instagram reply window has closed. A person can reply within 7 days of the customer's last message; automated replies only within 24 hours."
		)
	)


def plain(text):
	return strip_html(text or "").replace("\xa0", " ").strip()


def public_url(file_url):
	if file_url.startswith(("http://", "https://")):
		return file_url
	if file_url.startswith("/private/"):
		return media.share(file_url)
	return get_url(file_url)


def interactive_spec(doc):
	try:
		spec = json.loads(doc.buttons or "{}")
	except ValueError:
		return {}
	return spec if isinstance(spec, dict) else {}


def quick_replies(spec):
	return [
		{
			"content_type": "text",
			"title": row["title"][:20],
			"payload": str(row.get("id") or row["title"])[:1000],
		}
		for row in (spec.get("options") or [])[:QUICK_REPLY_LIMIT]
		if row.get("title")
	]


def message_body(doc):
	if doc.message_type == "Template" or doc.use_template:
		frappe.throw(_("Templates are only available on WhatsApp."))
	if doc.content_type in ATTACHMENT and doc.attach:
		return {
			"attachment": {"type": ATTACHMENT[doc.content_type], "payload": {"url": public_url(doc.attach)}}
		}
	text = plain(doc.message)
	spec = interactive_spec(doc) if doc.content_type == "interactive" else {}
	if spec.get("type") == "cta_url" and spec.get("url"):
		text = "\n".join(part for part in (text, spec["url"]) if part)
	if not text:
		frappe.throw(_("Write a message to send on Instagram."))
	body = {"text": text[:TEXT_LIMIT]}
	replies = quick_replies(spec) if spec.get("type") != "cta_url" else []
	if replies:
		body["quick_replies"] = replies
	return body


def reaction_body(doc):
	if not doc.reply_to_message_id:
		frappe.throw(_("Pick a message to react to."))
	if not doc.message:
		return {"sender_action": "unreact", "payload": {"message_id": doc.reply_to_message_id}}
	return {
		"sender_action": "react",
		"payload": {"message_id": doc.reply_to_message_id, "reaction": "love"},
	}


SENT_SECONDS = 600


def sent_key(mid):
	return f"onechat:instagram-sent:{mid}"


def sent_by_onechat(mid):
	return bool(mid and frappe.cache().get_value(sent_key(mid)))


def post(account, body):
	try:
		response = graph.send(account, body)
	except (graph.GraphError, requests.RequestException) as error:
		frappe.throw(str(error), title=_("Instagram"))
	if response.get("message_id"):
		frappe.cache().set_value(sent_key(response["message_id"]), 1, expires_in_sec=SENT_SECONDS)
	return response


def deliver(doc):
	account = graph.account_doc(doc.whatsapp_account)
	contact = contact_of(doc)
	if not doc.to and contact:
		doc.to = frappe.db.get_value(CONTACT, contact, "instagram_id")
	if not doc.to:
		frappe.throw(_("This contact has no Instagram ID."))

	if doc.get("reply_to_comment"):
		private_reply(doc, account)
		return

	allowed = rules(doc, contact)
	recipient = {"recipient": {"id": doc.to}}

	if doc.content_type == "reaction":
		post(account, {**recipient, **reaction_body(doc)})
		doc.status = "sent"
		return

	response = post(account, {**recipient, **allowed, "message": message_body(doc)})
	doc.message_id = response.get("message_id")
	doc.message_tag = allowed.get("tag")
	doc.status = "sent"

	caption = plain(doc.message) if doc.content_type in ATTACHMENT and doc.attach else ""
	if caption:
		post(account, {**recipient, **allowed, "message": {"text": caption[:TEXT_LIMIT]}})


def private_reply(doc, account):
	from onechat.instagram import comments

	comment = frappe.db.get_value(
		MESSAGE,
		{"message_id": doc.reply_to_comment, "content_type": "comment"},
		["name", "comment_replied", "creation"],
		as_dict=True,
	)
	if not comment:
		frappe.throw(_("The comment to reply to was not found."))
	comments.check_private_reply(comment)
	response = post(
		account, {"recipient": {"comment_id": doc.reply_to_comment}, "message": message_body(doc)}
	)
	doc.message_id = response.get("message_id")
	doc.status = "sent"
	frappe.db.set_value(MESSAGE, comment.name, "comment_replied", 1, update_modified=False)
