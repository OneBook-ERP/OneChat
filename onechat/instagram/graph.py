import frappe
import requests
from frappe import _

ACCOUNT = "OneChat Account"
BASE_URL = "https://graph.instagram.com"
VERSION = "v25.0"
TIMEOUT = 20
WEBHOOK_FIELDS = "messages,messaging_postbacks,messaging_seen,message_reactions,messaging_referral,comments"
MEDIA_FIELDS = "id,caption,media_type,media_product_type,thumbnail_url,media_url,permalink,timestamp"


class GraphError(frappe.ValidationError):
	pass


def account_doc(account):
	return account if hasattr(account, "get_password") else frappe.get_doc(ACCOUNT, account)


def base_url(account):
	url = (account.get("url") or "").rstrip("/")
	return url if "instagram" in url else BASE_URL


def version(account):
	return account.get("version") or VERSION


def error_text(data, response):
	error = (data or {}).get("error") or {}
	message = error.get("error_user_msg") or error.get("message") or response.reason
	code = error.get("code")
	return f"{message} ({code})" if code else message


def call(account, method, path, params=None, payload=None, versioned=True, token=None):
	account = account_doc(account)
	root = f"{base_url(account)}/{version(account)}" if versioned else base_url(account)
	headers = {"Authorization": f"Bearer {token or account.get_password('token')}"}
	response = requests.request(
		method, f"{root}/{path.lstrip('/')}", params=params, json=payload, headers=headers, timeout=TIMEOUT
	)
	try:
		data = response.json()
	except ValueError:
		data = {}
	if response.status_code >= 400 or (isinstance(data, dict) and data.get("error")):
		raise GraphError(_("Instagram: {0}").format(error_text(data, response)))
	return data


def profile(account):
	return call(account, "GET", "me", {"fields": "user_id,username,name,profile_picture_url"})


def subscribe(account):
	return call(account, "POST", "me/subscribed_apps", {"subscribed_fields": WEBHOOK_FIELDS})


def user_profile(account, instagram_id):
	return call(account, "GET", instagram_id, {"fields": "name,username,profile_pic"})


def send(account, payload):
	account = account_doc(account)
	return call(account, "POST", f"{account.ig_user_id or 'me'}/messages", payload=payload)


def refresh(account):
	account = account_doc(account)
	return call(
		account,
		"GET",
		"refresh_access_token",
		{"grant_type": "ig_refresh_token", "access_token": account.get_password("token")},
		versioned=False,
	)


def reply_to_comment(account, comment_id, text):
	return call(account, "POST", f"{comment_id}/replies", {"message": text})


def hide_comment(account, comment_id, hidden=True):
	return call(account, "POST", comment_id, {"hide": "true" if hidden else "false"})


def media(account, media_id):
	return call(account, "GET", media_id, {"fields": MEDIA_FIELDS})


def recent_media(account, limit=24):
	return call(account, "GET", "me/media", {"fields": MEDIA_FIELDS, "limit": limit}).get("data") or []
