import hashlib
import hmac
import json
import mimetypes

import frappe
import requests
from frappe.utils import add_days, now_datetime
from frappe.utils.password import get_decrypted_password
from werkzeug.wrappers import Response

from onechat.campaigns import chat_links
from onechat.campaigns.forms import resolve_form
from onechat.insights.costs import announce, record_pricing
from onechat.utils import get_whatsapp_account
from onechat.whatsapp import accounts, pay

ACCOUNT = "OneChat Account"
MESSAGE = "OneChat Message"
LOG = "WhatsApp Notification Log"
STATUS_RANK = {"sent": 1, "delivered": 2, "read": 3}
LOG_DAYS = 7
MEDIA_TYPES = ("image", "audio", "video", "document", "sticker")


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

	for entry_id, change in changes(payload):
		handle_change(change, entry_id)

	return Response("OK", status=200)


def verify():
	token = frappe.form_dict.get("hub.verify_token")
	if not token or not frappe.db.exists(ACCOUNT, {"webhook_verify_token": token}):
		return Response("Verify token does not match", status=403)

	accounts.mark_verified(token)
	return Response(frappe.form_dict.get("hub.challenge"), status=200)


def app_secrets():
	secrets = set()
	for name in frappe.get_all(ACCOUNT, filters={"channel": ["!=", "Instagram"]}, pluck="name"):
		secret = get_decrypted_password(ACCOUNT, name, "app_secret", raise_exception=False)
		if secret:
			secrets.add(secret)

	return secrets


def warn_unsigned():
	key = "onechat:webhook-no-secret"
	if frappe.cache().get_value(key):
		return
	frappe.cache().set_value(key, 1, expires_in_sec=3600)
	frappe.log_error(
		title="WhatsApp webhook rejected",
		message="No WhatsApp account has an app secret, so webhook calls can't be verified and are rejected. Add the app secret in Settings → Accounts.",
	)


def signed():
	secrets = app_secrets()
	if not secrets:
		warn_unsigned()
		return False

	header = frappe.get_request_header("X-Hub-Signature-256") or ""
	if not header.startswith("sha256="):
		return False

	body = frappe.request.get_data()
	received = header.split("=", 1)[1]
	return any(
		hmac.compare_digest(hmac.new(secret.encode(), body, hashlib.sha256).hexdigest(), received)
		for secret in secrets
	)


def changes(payload):
	entries = payload.get("entry") or []
	if isinstance(entries, dict):
		entries = [entries]

	for entry in entries:
		for change in entry.get("changes") or []:
			yield entry.get("id"), change


def handle_change(change, entry_id=None):
	handlers = {
		"messages": handle_messages,
		"message_template_status_update": update_template_status,
		"message_template_quality_update": update_template_quality,
	}
	account_handlers = {
		"phone_number_quality_update": accounts.on_quality_update,
		"phone_number_name_update": accounts.on_name_update,
		"account_update": accounts.on_account_update,
		"payment_configuration_update": pay.on_configuration_update,
	}
	field = change.get("field")
	value = change.get("value") or {}
	if field in handlers:
		safely(handlers[field], value)
	elif field in account_handlers:
		safely(account_handlers[field], value, entry_id)


def safely(handler, value, *args):
	frappe.db.savepoint("onechat_webhook")
	try:
		handler(value, *args)
	except Exception:
		frappe.db.rollback(save_point="onechat_webhook")
		frappe.log_error(
			title=f"WhatsApp webhook: {handler.__name__}",
			message=f"{frappe.get_traceback()}\n\n{json.dumps(value, default=str)[:20000]}",
		)


def handle_messages(value):
	phone_id = (value.get("metadata") or {}).get("phone_number_id")
	if not phone_id or frappe.db.get_value(ACCOUNT, {"phone_id": phone_id}, "status") == "Inactive":
		return

	account = get_whatsapp_account(phone_id)
	if not account:
		return

	accounts.touch(account.name)

	profiles = {
		row.get("wa_id"): (row.get("profile") or {}).get("name") for row in value.get("contacts") or []
	}
	for message in value.get("messages") or []:
		safely(receive, message, account, profiles.get(message.get("from")))

	for status in value.get("statuses") or []:
		safely(pay.on_status if status.get("type") == "payment" else update_message_status, status)


def receive(message, account, profile_name):
	if frappe.db.exists(MESSAGE, {"message_id": message.get("id")}):
		return

	kind = message.get("type")
	context = message.get("context") or {}
	is_reply = bool(context.get("id")) and not context.get("forwarded")
	base = {
		"doctype": MESSAGE,
		"type": "Incoming",
		"from": message.get("from"),
		"message_id": message.get("id"),
		"reply_to_message_id": context.get("id") if is_reply else None,
		"is_reply": is_reply,
		"profile_name": profile_name,
		"whatsapp_account": account.name,
		"referral": json.dumps(message["referral"]) if message.get("referral") else None,
	}

	if kind == "text":
		text, link = chat_links.detect(message["text"]["body"])
		insert(base, message=text, content_type="text", chat_link=link)
	elif kind == "reaction":
		reaction = message["reaction"]
		insert(
			base,
			message=reaction.get("emoji"),
			reply_to_message_id=reaction.get("message_id"),
			is_reply=False,
			content_type="reaction",
		)
	elif kind == "interactive":
		receive_interactive(message, base, account)
	elif kind in MEDIA_TYPES:
		receive_media(message, base, account)
	elif kind == "order":
		from onechat.integrations.erpnext_commerce import handle_order, order_summary

		handle_order(
			insert(
				base,
				message=order_summary(message["order"]),
				content_type="order",
				products=json.dumps(message["order"]),
			)
		)
	elif kind == "button":
		button = message["button"]
		insert(
			base,
			message=button.get("text"),
			content_type="button",
			buttons=json.dumps({"reply_id": button.get("payload")}),
		)
	elif kind == "location":
		location = message.get("location") or {}
		insert(
			base,
			message="\n".join(part for part in (location.get("name"), location.get("address")) if part)
			or None,
			content_type="location",
			latitude=location.get("latitude"),
			longitude=location.get("longitude"),
		)
	else:
		body = message.get(kind)
		insert(base, message=body.get(kind) if isinstance(body, dict) else None, content_type=kind)


def insert(base, **values):
	return frappe.get_doc({**base, **values}).insert(ignore_permissions=True)


def receive_interactive(message, base, account):
	data = message.get("interactive") or {}
	kind = data.get("type")

	if kind in ("button_reply", "list_reply"):
		reply = data[kind]
		insert(
			base,
			message=reply.get("title") or reply.get("id"),
			content_type="button",
			buttons=json.dumps({"reply_id": reply.get("id")}),
		)
		return

	if kind != "nfm_reply":
		return

	try:
		response = json.loads((data.get("nfm_reply") or {}).get("response_json") or "{}")
	except ValueError:
		response = {}

	summary = (
		", ".join(f"{key}: {value}" for key, value in response.items() if value and key != "flow_token")
		or "Flow completed"
	)
	flow = resolve_form(response, base.get("reply_to_message_id"))

	insert(base, message=summary, content_type="flow", flow=flow, flow_response=json.dumps(response))
	frappe.publish_realtime(
		"whatsapp_flow_response",
		{
			"phone": message.get("from"),
			"message_id": message.get("id"),
			"flow_response": response,
			"whatsapp_account": account.name,
		},
		room="doctype:OneChat Contact",
	)


def receive_media(message, base, account):
	kind = message["type"]
	media = message.get(kind) or {}
	doc = insert(base, message=media.get("caption", ""), content_type="image" if kind == "sticker" else kind)

	try:
		content, mime = download_media(account, media.get("id"))
	except Exception:
		frappe.log_error(
			title="WhatsApp webhook: media download", reference_doctype=MESSAGE, reference_name=doc.name
		)
		return

	extension = mimetypes.guess_extension((mime or "").split(";")[0].strip()) or ""
	file = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": media.get("filename") or f"{frappe.generate_hash(length=10)}{extension}",
			"attached_to_doctype": MESSAGE,
			"attached_to_name": doc.name,
			"attached_to_field": "attach",
			"content": content,
		}
	).save(ignore_permissions=True)

	doc.attach = file.file_url
	doc.save(ignore_permissions=True)


def download_media(account, media_id):
	headers = {"Authorization": f"Bearer {account.get_password('token')}"}
	info = requests.get(f"{account.url}/{account.version}/{media_id}/", headers=headers, timeout=20)
	info.raise_for_status()
	data = info.json()

	response = requests.get(data["url"], headers=headers, timeout=60)
	response.raise_for_status()
	return response.content, data.get("mime_type")


def failure_reason(status):
	errors = status.get("errors") or []
	if not errors:
		return None

	error = errors[0]
	title = error.get("title") or error.get("message") or "Error"
	details = (error.get("error_data") or {}).get("details")
	text = f"{title} ({error['code']})" if error.get("code") else title
	return f"{text}: {details}" if details and details != title else text


def update_message_status(status):
	name = frappe.db.get_value(MESSAGE, {"message_id": status.get("id")})
	if not name:
		return

	new = (status.get("status") or "").lower()
	doc = frappe.get_doc(MESSAGE, name)
	priced = record_pricing(doc, status)
	if new != "failed" and STATUS_RANK.get((doc.status or "").lower(), 0) >= STATUS_RANK.get(new, 0):
		if priced:
			doc.save(ignore_permissions=True)
			announce(doc)
		return

	doc.status = new
	conversation = (status.get("conversation") or {}).get("id")
	if conversation:
		doc.conversation_id = conversation
	if new == "failed":
		doc.error_message = failure_reason(status)
	doc.save(ignore_permissions=True)
	if priced:
		announce(doc)


def update_template_status(data):
	template = frappe.qb.DocType("WhatsApp Templates")
	reason = data.get("reason")
	(
		frappe.qb.update(template)
		.set(template.status, data["event"])
		.set(template.rejected_reason, reason if reason and reason != "NONE" else None)
		.where(template.id == str(data["message_template_id"]))
		.run()
	)


def update_template_quality(data):
	template = frappe.qb.DocType("WhatsApp Templates")
	(
		frappe.qb.update(template)
		.set(template.quality_score, data.get("new_quality_score") or "UNKNOWN")
		.set(template.quality_updated_at, now_datetime())
		.where(template.id == str(data.get("message_template_id")))
		.run()
	)


def purge_logs():
	frappe.db.delete(LOG, {"template": "Webhook", "creation": ["<", add_days(now_datetime(), -LOG_DAYS)]})
