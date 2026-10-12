import frappe
import requests
from frappe import _
from frappe.utils import add_to_date, cint, get_datetime, now_datetime

from onechat.instagram import graph
from onechat.whatsapp.accounts import set_alert

ACCOUNT = "OneChat Account"
REFRESH_BEFORE_DAYS = 20


def missing(account):
	if not account.get_password("token", raise_exception=False):
		return _("Add the Instagram access token.")
	if not account.get_password("app_secret", raise_exception=False):
		return _("Add the app secret so Instagram webhooks can be verified.")
	if not account.webhook_verify_token:
		return _("Add a webhook verify token.")
	return None


def run_check(account):
	values = {"last_checked_at": now_datetime()}
	problem = missing(account)

	if not problem:
		try:
			me = graph.profile(account)
			user_id = str(me.get("user_id") or me.get("id") or "")
			if account.ig_user_id and user_id and account.ig_user_id != user_id:
				problem = _("This token belongs to Instagram account {0}, not {1}.").format(
					user_id, account.ig_user_id
				)
			else:
				values.update(
					{
						"ig_user_id": user_id or account.ig_user_id,
						"ig_username": me.get("username"),
					}
				)
				graph.subscribe(account)
		except requests.RequestException:
			problem = _("Could not reach Instagram. Check the server's internet access.")
		except graph.GraphError as error:
			problem = str(error)

	values.update(
		{
			"connection_status": "Error" if problem else "Connected",
			"connection_message": problem
			or _("Token is valid and the account is subscribed to message webhooks."),
		}
	)
	frappe.db.set_value(ACCOUNT, account.name, values, update_modified=False)
	return values


def instagram_accounts():
	return frappe.get_all(ACCOUNT, filters={"status": "Active", "channel": "Instagram"}, pluck="name")


def due(account):
	expires = get_datetime(account.token_expires_at) if account.token_expires_at else None
	return not expires or expires <= add_to_date(now_datetime(), days=REFRESH_BEFORE_DAYS)


def refresh_token(account):
	data = graph.refresh(account)
	account.token = data["access_token"]
	account.token_expires_at = add_to_date(now_datetime(), seconds=cint(data.get("expires_in")))
	account.save(ignore_permissions=True)


def refresh_tokens():
	for name in instagram_accounts():
		account = frappe.get_doc(ACCOUNT, name)
		if not due(account):
			continue
		try:
			refresh_token(account)
			frappe.db.commit()  # nosemgrep: frappe-manual-commit - commit refreshed access token per account
		except Exception as error:
			frappe.db.rollback()
			frappe.log_error(
				title="Instagram token refresh",
				reference_doctype=ACCOUNT,
				reference_name=name,
			)
			set_alert(
				name,
				"Warning" if account.token_expires_at else "Info",
				_("The Instagram token could not be refreshed: {0}").format(str(error)),
			)
