import secrets
from urllib.parse import urlencode

import frappe
import requests
from frappe import _
from frappe.utils import add_to_date, cint, get_url, now_datetime

from onechat.instagram import accounts, graph
from onechat.whatsapp.accounts import admin_only

ACCOUNT = "OneChat Account"
AUTHORIZE_URL = "https://www.instagram.com/oauth/authorize"
TOKEN_URL = "https://api.instagram.com/oauth/access_token"
SCOPES = "instagram_business_basic,instagram_business_manage_messages,instagram_business_manage_comments"
STATE_SECONDS = 600


def redirect_uri():
	return get_url("/api/method/onechat.instagram.oauth.callback")


def state_key(state):
	return f"onechat:instagram-oauth:{state}"


@frappe.whitelist()
def callback_url():
	admin_only()
	return redirect_uri()


@frappe.whitelist(methods=["POST"])
def start(name: str):
	admin_only()
	account = frappe.get_doc(ACCOUNT, name)
	if account.channel != "Instagram":
		frappe.throw(_("{0} is not an Instagram account.").format(name))
	if not account.app_id or not account.get_password("app_secret", raise_exception=False):
		frappe.throw(_("Save the Instagram app ID and app secret first."))

	state = secrets.token_urlsafe(24)
	frappe.cache().set_value(
		state_key(state), {"account": name, "user": frappe.session.user}, expires_in_sec=STATE_SECONDS
	)
	query = {
		"client_id": account.app_id,
		"redirect_uri": redirect_uri(),
		"response_type": "code",
		"scope": SCOPES,
		"state": state,
		"force_reauth": "true",
	}
	return f"{AUTHORIZE_URL}?{urlencode(query)}"


@frappe.whitelist(methods=["GET"])
def callback(
	code: str | None = None,
	state: str | None = None,
	error: str | None = None,
	error_description: str | None = None,
	**kwargs,
):
	pending = None
	if state:
		pending = frappe.cache().get_value(state_key(state))
		frappe.cache().delete_value(state_key(state))
	if not pending or pending.get("user") != frappe.session.user:
		return finish(None, _("This Instagram sign-in expired or was started by someone else. Try again."))

	name = pending["account"]
	if error or not code:
		return finish(name, error_description or _("Instagram sign-in was cancelled."))

	try:
		connect(frappe.get_doc(ACCOUNT, name), code.split("#")[0])
	except (requests.RequestException, graph.GraphError, KeyError) as problem:
		frappe.log_error(title="Instagram sign-in", reference_doctype=ACCOUNT, reference_name=name)
		return finish(name, str(problem) or _("Could not connect to Instagram."))
	return finish(name, None)


def parse(response):
	try:
		data = response.json()
	except ValueError:
		data = {}
	if response.status_code >= 400 or data.get("error") or data.get("error_message"):
		error = data.get("error") if isinstance(data.get("error"), dict) else {}
		message = data.get("error_message") or error.get("message") or response.reason
		raise graph.GraphError(_("Instagram: {0}").format(message))
	return data


def connect(account, code):
	secret = account.get_password("app_secret")
	short = parse(
		requests.post(
			TOKEN_URL,
			data={
				"client_id": account.app_id,
				"client_secret": secret,
				"grant_type": "authorization_code",
				"redirect_uri": redirect_uri(),
				"code": code,
			},
			timeout=graph.TIMEOUT,
		)
	)
	long = parse(
		requests.get(
			f"{graph.BASE_URL}/access_token",
			params={
				"grant_type": "ig_exchange_token",
				"client_secret": secret,
				"access_token": short["access_token"],
			},
			timeout=graph.TIMEOUT,
		)
	)

	account.token = long["access_token"]
	account.token_expires_at = add_to_date(now_datetime(), seconds=cint(long.get("expires_in")))
	account.ig_user_id = None
	account.save(ignore_permissions=True)
	accounts.run_check(frappe.get_doc(ACCOUNT, account.name))


def finish(name, problem):
	query = {"settings": "accounts", "instagram": "error" if problem else "connected"}
	if name:
		query["account"] = name
	if problem:
		query["message"] = str(problem)[:300]
	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = f"/onechat?{urlencode(query)}"
