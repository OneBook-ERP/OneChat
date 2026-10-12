import mimetypes

import frappe
import requests
from frappe import _
from frappe.utils import get_url

ACCOUNT = "OneChat Account"
TIMEOUT = 120
MEDIA_DAYS = 25


def private(file_url):
	return (file_url or "").startswith("/private/")


def absolute(file_url):
	if not file_url or file_url.startswith("http"):
		return file_url
	return get_url(file_url if file_url.startswith("/") else f"/{file_url}")


def upload(account_name, file_url):
	key = f"onechat:media:{account_name}:{file_url}"
	cached = frappe.cache().get_value(key)
	if cached:
		return cached

	name = frappe.db.get_value("File", {"file_url": file_url}, "name")
	if not name:
		frappe.throw(_("The file {0} was not found.").format(file_url))
	file = frappe.get_doc("File", name)
	content = file.get_content()
	if isinstance(content, str):
		content = content.encode()
	mime = mimetypes.guess_type(file.file_name or file_url)[0] or "application/octet-stream"

	account = frappe.get_doc(ACCOUNT, account_name)
	response = requests.post(
		f"{account.url}/{account.version}/{account.phone_id}/media",
		headers={"Authorization": f"Bearer {account.get_password('token')}"},
		data={"messaging_product": "whatsapp", "type": mime},
		files={"file": (file.file_name or "file", content, mime)},
		timeout=TIMEOUT,
	)
	try:
		body = response.json()
	except ValueError:
		body = {}
	if not response.ok or not body.get("id"):
		error = body.get("error") or {}
		frappe.throw(
			_("WhatsApp could not take the private file: {0}").format(
				error.get("message") or response.text[:200]
			)
		)

	frappe.cache().set_value(key, body["id"], expires_in_sec=MEDIA_DAYS * 86400)
	return body["id"]


def reference(account_name, file_url):
	if private(file_url) and account_name:
		return {"id": upload(account_name, file_url)}
	return {"link": absolute(file_url)}
