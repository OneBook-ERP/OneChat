import hashlib
import hmac
import json
import mimetypes

import frappe
import requests
from frappe.utils.password import get_decrypted_password
from werkzeug.wrappers import Response

from onechat.inbox.conversations import CONTACT, find_instagram_contact, publish
from onechat.instagram import comments, graph
from onechat.instagram.send import sent_by_onechat
from onechat.whatsapp import accounts
from onechat.whatsapp.webhook import safely, update_message_status

ACCOUNT = "OneChat Account"
MESSAGE = "OneChat Message"
LINK = "OneChat Chat Link"
REFERRAL_SECONDS = 600
SEEN_SECONDS = 900
MEDIA = {"image": "image", "video": "video", "audio": "audio", "file": "document"}
SHARES = ("share", "ig_reel", "reel", "ig_post", "post")
REACTIONS = {
	"love": "❤️",
	"like": "👍",
	"laugh": "😆",
	"wow": "😮",
	"sad": "😢",
	"angry": "😠",
}


@frappe.whitelist(allow_guest=True)
def webhook():
	if frappe.request.method == "GET":
		return verify()

	if not signed():
		return Response("Invalid signature", status=403)

	try:
		payload = json.loads(frappe.request.get_data(as_text=True) or "{}")
	except ValueError:
		return Response("Invalid payload", status=400)

	if payload.get("object") == "instagram":
		for account, event in events(payload):
			safely(handle, event, account)
		for account, value in comment_events(payload):
			safely(receive_comment, value, account)

	return Response("OK", status=200)


def instagram_accounts(**filters):
	return frappe.get_all(ACCOUNT, filters={"channel": "Instagram", **filters}, pluck="name")


def verify():
	token = frappe.form_dict.get("hub.verify_token")
	if not token or not instagram_accounts(webhook_verify_token=token):
		return Response("Verify token does not match", status=403)

	accounts.mark_verified(token)
	return Response(frappe.form_dict.get("hub.challenge"), status=200)


def app_secrets():
	secrets = set()
	for name in instagram_accounts():
		secret = get_decrypted_password(ACCOUNT, name, "app_secret", raise_exception=False)
		if secret:
			secrets.add(secret)
	return secrets


def signed():
	header = frappe.get_request_header("X-Hub-Signature-256") or ""
	if not header.startswith("sha256="):
		return False

	body = frappe.request.get_data()
	received = header.split("=", 1)[1]
	return any(
		hmac.compare_digest(hmac.new(secret.encode(), body, hashlib.sha256).hexdigest(), received)
		for secret in app_secrets()
	)


def events(payload):
	entries = payload.get("entry") or []
	if isinstance(entries, dict):
		entries = [entries]

	for entry in entries:
		account = account_for(entry.get("id"))
		if not account:
			continue
		accounts.touch(account.name)
		for event in entry.get("messaging") or []:
			yield account, event


def comment_events(payload):
	entries = payload.get("entry") or []
	if isinstance(entries, dict):
		entries = [entries]
	for entry in entries:
		changes = [
			change
			for change in entry.get("changes") or []
			if change.get("field") in ("comments", "live_comments")
		]
		account = account_for(entry.get("id")) if changes else None
		if not account:
			continue
		for change in changes:
			yield account, change.get("value") or {}


def account_for(ig_user_id):
	name = ig_user_id and frappe.db.get_value(
		ACCOUNT, {"channel": "Instagram", "ig_user_id": str(ig_user_id)}
	)
	return frappe.get_doc(ACCOUNT, name) if name else None


def claim(key):
	if not key:
		return True
	cache_key = f"onechat:ig-event:{key}"
	cache = frappe.cache()
	if cache.get_value(cache_key):
		return False
	cache.set_value(cache_key, 1, expires_in_sec=SEEN_SECONDS)
	return True


def release(key):
	if key:
		frappe.cache().delete_value(f"onechat:ig-event:{key}")


def event_key(event):
	if "message" in event:
		return event["message"].get("mid")
	if "reaction" in event:
		reaction = event["reaction"]
		return f"reaction:{party_of(event)}:{reaction.get('mid')}:{reaction.get('action')}:{event.get('timestamp')}"
	if "postback" in event:
		return event["postback"].get("mid") or f"postback:{party_of(event)}:{event.get('timestamp')}"
	return None


def once(key, handler, *args):
	if not claim(key):
		return
	try:
		handler(*args)
	except Exception:
		release(key)
		raise


def receive_comment(value, account):
	once(
		f"comment:{value.get('id')}" if value.get("id") else None,
		comments.receive,
		value,
		account,
	)


def handle(event, account):
	once(event_key(event), dispatch, event, account)


def dispatch(event, account):
	if "message" in event:
		receive_message(event, account)
	elif "reaction" in event:
		receive_reaction(event, account)
	elif "read" in event:
		receive_read(event, account)
	elif "postback" in event:
		receive_postback(event, account)
	elif "referral" in event:
		remember_referral(event, account)


def party_of(event):
	return str((event.get("sender") or {}).get("id") or "")


def base(event, account, mid):
	message = event.get("message") or {}
	reply_to = message.get("reply_to") or {}
	party = party_of(event)
	return {
		"doctype": MESSAGE,
		"type": "Incoming",
		"from": party,
		"message_id": mid,
		"is_reply": bool(reply_to.get("mid")),
		"reply_to_message_id": reply_to.get("mid"),
		"profile_name": profile_name(account, party),
		"whatsapp_account": account.name,
	}


def insert(values, **extra):
	doc = frappe.get_doc({**values, **extra})
	doc.flags.skip_send = True
	return doc.insert(ignore_permissions=True)


def profile_name(account, party):
	contact = find_instagram_contact(party, account.name)
	if contact:
		return frappe.db.get_value(CONTACT, contact, "contact_name")
	details = lookup(account, party)
	return details.get("name") or details.get("username") or party


def lookup(account, party):
	key = f"onechat:instagram-profile:{account.name}:{party}"
	cache = frappe.cache()
	cached = cache.get_value(key)
	if cached is not None:
		return cached
	try:
		details = graph.user_profile(account, party)
	except (graph.GraphError, requests.RequestException):
		details = {}
	cache.set_value(key, details, expires_in_sec=86400)
	return details


def remember_username(doc, account, party):
	details = lookup(account, party)
	contact = doc.get("whatsapp_contact")
	if not contact:
		return
	current = (
		frappe.db.get_value(CONTACT, contact, ["instagram_username", "profile_image"], as_dict=True) or {}
	)
	if details.get("username") and not current.get("instagram_username"):
		frappe.db.set_value(
			CONTACT,
			contact,
			"instagram_username",
			details["username"],
			update_modified=False,
		)
	if details.get("profile_pic") and not current.get("profile_image"):
		frappe.enqueue(
			"onechat.instagram.webhook.save_avatar",
			queue="short",
			enqueue_after_commit=True,
			contact=contact,
			url=details["profile_pic"],
		)


def save_avatar(contact, url):
	if frappe.db.get_value(CONTACT, contact, "profile_image"):
		return
	try:
		response = requests.get(url, timeout=30)
		response.raise_for_status()
	except requests.RequestException:
		return
	extension = (
		mimetypes.guess_extension((response.headers.get("content-type") or "").split(";")[0].strip())
		or ".jpg"
	)
	file = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": f"instagram-{frappe.generate_hash(length=10)}{extension}",
			"attached_to_doctype": CONTACT,
			"attached_to_name": contact,
			"attached_to_field": "profile_image",
			"is_private": 1,
			"content": response.content,
		}
	).save(ignore_permissions=True)
	frappe.db.set_value(CONTACT, contact, "profile_image", file.file_url, update_modified=False)


def receive_message(event, account):
	message = event["message"]
	mid = message.get("mid")
	if not mid:
		return
	if message.get("is_deleted"):
		mark_deleted(mid)
		return
	if frappe.db.exists(MESSAGE, {"message_id": mid}):
		return
	if message.get("is_echo"):
		frappe.enqueue(
			"onechat.instagram.webhook.receive_echo",
			payload=event,
			account=account.name,
			enqueue_after_commit=True,
		)
		return

	values = base(event, account, mid)
	referral = message.get("referral") or pending_referral(account, party_of(event))
	if referral:
		values["referral"] = json.dumps(referral)
		values["chat_link"] = chat_link_for(referral)
	story = (message.get("reply_to") or {}).get("story") or {}
	if story:
		values.update(is_reply=False, reply_to_message_id=None)

	quick_reply = message.get("quick_reply") or {}
	attachments = message.get("attachments") or []
	text = message.get("text") or ""

	if quick_reply:
		doc = insert(
			values,
			message=text,
			content_type="button",
			buttons=json.dumps({"reply_id": quick_reply.get("payload")}),
		)
	elif story:
		doc = insert(values, message=text, content_type="story_reply", link_url=story.get("url"))
	elif attachments:
		doc = receive_attachments(values, attachments, text, account)
	else:
		doc = insert(values, message=text, content_type="text")

	remember_username(doc, account, party_of(event))
	if doc.content_type == "story_mention":
		frappe.enqueue(
			"onechat.instagram.stories.thank",
			queue="short",
			enqueue_after_commit=True,
			message=doc.name,
		)


def receive_attachments(values, attachments, text, account):
	first = None
	for index, attachment in enumerate(attachments):
		kind = attachment.get("type")
		url = (attachment.get("payload") or {}).get("url")
		row = {
			**values,
			"message_id": (values["message_id"] if index == 0 else f"{values['message_id']}:{index}"),
		}
		caption = text if index == 0 else ""
		if kind == "story_mention":
			doc = insert(row, message=caption, content_type="story_mention", link_url=url)
		elif kind in MEDIA:
			doc = insert(row, message=caption, content_type=MEDIA[kind])
			if url:
				frappe.enqueue(
					"onechat.instagram.webhook.attach_media",
					queue="short",
					enqueue_after_commit=True,
					message=doc.name,
					url=url,
				)
		else:
			content_type = "share" if kind in SHARES else "text"
			doc = insert(
				row,
				message=caption or url or "",
				content_type=content_type,
				link_url=url,
			)
		first = first or doc
	return first


def attach_media(message, url):
	try:
		response = requests.get(url, timeout=60)
		response.raise_for_status()
	except requests.RequestException:
		frappe.log_error(
			title="Instagram webhook: media download",
			reference_doctype=MESSAGE,
			reference_name=message,
		)
		return

	mime = (response.headers.get("content-type") or "").split(";")[0].strip()
	extension = mimetypes.guess_extension(mime) or ""
	file = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": f"{frappe.generate_hash(length=10)}{extension}",
			"attached_to_doctype": MESSAGE,
			"attached_to_name": message,
			"attached_to_field": "attach",
			"is_private": 1,
			"content": response.content,
		}
	).save(ignore_permissions=True)
	frappe.db.set_value(MESSAGE, message, "attach", file.file_url, update_modified=False)
	contact = frappe.db.get_value(MESSAGE, message, "whatsapp_contact")
	if contact:
		publish(contact, message)


def receive_echo(payload, account):
	event = payload
	message = event.get("message") or {}
	mid = message.get("mid")
	if not mid or sent_by_onechat(mid) or frappe.db.exists(MESSAGE, {"message_id": mid}):
		return
	account = frappe.get_doc(ACCOUNT, account)
	party = str((event.get("recipient") or {}).get("id") or "")
	attachments = message.get("attachments") or []
	kind = attachments[0].get("type") if attachments else None
	insert(
		{
			"doctype": MESSAGE,
			"type": "Outgoing",
			"to": party,
			"message_id": mid,
			"whatsapp_account": account.name,
			"source": "Agent",
			"status": "sent",
			"is_echo": 1,
		},
		message=message.get("text") or "",
		content_type=MEDIA.get(kind, "text"),
		link_url=((attachments[0].get("payload") or {}).get("url") if attachments else None),
	)


def receive_reaction(event, account):
	reaction = event["reaction"]
	target = reaction.get("mid")
	if not target:
		return
	emoji = ""
	if reaction.get("action") != "unreact":
		emoji = reaction.get("emoji") or REACTIONS.get(reaction.get("reaction"), "❤️")
	insert(
		base(
			event,
			account,
			f"{target}:reaction:{party_of(event)}:{event.get('timestamp')}",
		),
		message=emoji,
		content_type="reaction",
		is_reply=False,
		reply_to_message_id=target,
	)


def receive_read(event, account):
	target = (event.get("read") or {}).get("mid")
	contact = find_instagram_contact(party_of(event), account.name)
	if not target or not contact:
		return
	until = frappe.db.get_value(MESSAGE, {"message_id": target}, "creation")
	filters = {
		"whatsapp_contact": contact,
		"type": "Outgoing",
		"message_id": ["is", "set"],
		"status": ["not in", ["read", "failed"]],
	}
	if until:
		filters["creation"] = ["<=", until]
	for message_id in frappe.get_all(MESSAGE, filters=filters, pluck="message_id"):
		update_message_status({"id": message_id, "status": "read"})


def receive_postback(event, account):
	postback = event["postback"]
	insert(
		base(
			event,
			account,
			postback.get("mid") or f"postback:{party_of(event)}:{event.get('timestamp')}",
		),
		message=postback.get("title") or postback.get("payload"),
		content_type="button",
		buttons=json.dumps({"reply_id": postback.get("payload")}),
	)


def mark_deleted(mid):
	name = frappe.db.get_value(MESSAGE, {"message_id": mid})
	if name:
		frappe.db.set_value(
			MESSAGE,
			name,
			{"message": frappe._("This message was deleted"), "attach": None},
			update_modified=False,
		)


def referral_key(account, party):
	return f"onechat:instagram-referral:{account.name}:{party}"


def remember_referral(event, account):
	party = party_of(event)
	if party and event.get("referral"):
		frappe.cache().set_value(
			referral_key(account, party),
			event["referral"],
			expires_in_sec=REFERRAL_SECONDS,
		)


def pending_referral(account, party):
	key = referral_key(account, party)
	cache = frappe.cache()
	referral = cache.get_value(key)
	if referral:
		cache.delete_value(key)
	return referral


def chat_link_for(referral):
	code = str((referral or {}).get("ref") or "").strip().upper()
	return frappe.db.get_value(LINK, {"ref_code": code}) if code else None
