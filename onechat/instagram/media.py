import mimetypes
import secrets

import frappe
from frappe.utils import get_url
from werkzeug.wrappers import Response

TOKEN_SECONDS = 600


def token_key(token):
	return f"onechat:instagram-media:{token}"


def raw_content(file):
	try:
		content = file.get_content(encodings=[])
	except TypeError:
		content = file.get_content()
	return content.encode() if isinstance(content, str) else content


def share(file_url):
	token = secrets.token_urlsafe(32)
	frappe.cache().set_value(token_key(token), file_url, expires_in_sec=TOKEN_SECONDS)
	return get_url(f"/api/method/onechat.instagram.media.fetch?token={token}")


@frappe.whitelist(allow_guest=True, methods=["GET"])
def fetch(token: str | None = None):
	file_url = frappe.cache().get_value(token_key(token)) if token else None
	name = file_url and frappe.db.get_value("File", {"file_url": file_url})
	if not name:
		return Response("Not found", status=404)

	file = frappe.get_doc("File", name)
	return Response(
		raw_content(file),
		mimetype=mimetypes.guess_type(file.file_name or file_url)[0] or "application/octet-stream",
		headers={"Cache-Control": "no-store"},
	)
