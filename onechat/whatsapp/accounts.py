import frappe
import requests
from frappe import _
from frappe.utils import now_datetime

from onechat.api_types import JSON
from onechat.workspace.session import is_admin

ACCOUNT = "OneChat Account"
PHONE_FIELDS = "display_phone_number,verified_name,quality_rating,messaging_limit_tier,name_status"
PROFILE_FIELDS = "about,address,description,email,profile_picture_url,websites,vertical"
LIMITS = {
	"TIER_50": "50 / day",
	"TIER_250": "250 / day",
	"TIER_1K": "1,000 / day",
	"TIER_10K": "10,000 / day",
	"TIER_100K": "100,000 / day",
	"TIER_UNLIMITED": "Unlimited",
}
VERTICALS = [
	"UNDEFINED",
	"OTHER",
	"AUTO",
	"BEAUTY",
	"APPAREL",
	"EDU",
	"ENTERTAIN",
	"EVENT_PLAN",
	"FINANCE",
	"GROCERY",
	"GOVT",
	"HOTEL",
	"HEALTH",
	"NONPROFIT",
	"PROF_SERVICES",
	"RETAIL",
	"TRAVEL",
	"RESTAURANT",
	"NOT_A_BIZ",
]
PROFILE_LIMITS = {"about": 139, "address": 256, "description": 512, "email": 128}
LEVELS = {"Info": 1, "Warning": 2, "Critical": 3}
EVENT_THROTTLE = 300


def admin_only():
	if not is_admin():
		frappe.throw(_("Only OneChat admins can manage WhatsApp accounts."), frappe.PermissionError)


def token(account):
	return account.get_password("token", raise_exception=False) or ""


def graph(account, path, params=None, method="GET", payload=None):
	response = requests.request(
		method,
		f"{account.url}/{account.version}/{path}",
		params=params,
		json=payload,
		headers={"Authorization": f"Bearer {token(account)}"},
		timeout=30,
	)
	data = response.json() if response.content else {}
	if response.status_code != 200:
		error = data.get("error") or {}
		raise ValueError(
			error.get("error_user_msg")
			or error.get("message")
			or _("Meta returned HTTP {0}").format(response.status_code)
		)

	return data


def wrong_business_id(account):
	return _(
		"{0} is not a WhatsApp Business Account ID. In Meta, open WhatsApp Manager → Account tools → Phone numbers (or the app's WhatsApp → API Setup) and copy the WhatsApp Business Account ID, not the Business portfolio ID or the App ID."
	).format(account.business_id)


def is_wrong_node(message):
	return "nonexisting field" in (message or "") or "nonexisting edge" in (message or "")


def missing(account):
	labels = {
		"token": _("Access token"),
		"phone_id": _("Phone number ID"),
		"business_id": _("Business account ID"),
	}
	gaps = [
		label
		for field, label in labels.items()
		if not (token(account) if field == "token" else account.get(field))
	]
	return _("Missing: {0}").format(", ".join(gaps)) if gaps else None


def run_check(account):
	if account.get("channel") == "Instagram":
		from onechat.instagram.accounts import run_check as check_instagram

		return check_instagram(account)

	values = {"last_checked_at": now_datetime()}
	problem = missing(account)

	if not problem:
		try:
			phone = graph(account, account.phone_id, {"fields": PHONE_FIELDS})
			try:
				numbers = (
					graph(
						account, f"{account.business_id}/phone_numbers", {"fields": "id", "limit": 100}
					).get("data")
					or []
				)
			except ValueError as error:
				raise ValueError(wrong_business_id(account) if is_wrong_node(str(error)) else str(error))
			if numbers and account.phone_id not in {row.get("id") for row in numbers}:
				raise ValueError(
					_(
						"The phone number ID {0} does not belong to the WhatsApp Business Account {1}. Check both IDs in WhatsApp Manager."
					).format(account.phone_id, account.business_id)
				)
			values.update(
				{
					"display_phone_number": phone.get("display_phone_number"),
					"verified_name": phone.get("verified_name"),
					"quality_rating": (phone.get("quality_rating") or "").title() or None,
					"messaging_limit": LIMITS.get(
						phone.get("messaging_limit_tier"), phone.get("messaging_limit_tier")
					),
					"name_status": (phone.get("name_status") or "").replace("_", " ").title() or None,
				}
			)
		except requests.RequestException:
			problem = _("Could not reach Meta. Check the API URL and the server's internet access.")
		except ValueError as error:
			problem = str(error)

	values.update(
		{
			"connection_status": "Error" if problem else "Connected",
			"connection_message": problem or _("Token, phone number and business account are valid."),
		}
	)
	frappe.db.set_value(ACCOUNT, account.name, values, update_modified=False)
	return values


@frappe.whitelist(methods=["POST"])
def check(name: str):
	admin_only()
	return run_check(frappe.get_doc(ACCOUNT, name))


def check_all():
	for name in frappe.get_all(ACCOUNT, filters={"status": "Active"}, pluck="name"):
		try:
			run_check(frappe.get_doc(ACCOUNT, name))
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title="WhatsApp account check", reference_doctype=ACCOUNT, reference_name=name)


def refresh(name):
	run_check(frappe.get_doc(ACCOUNT, name))


def set_alert(name, level, text):
	current = frappe.db.get_value(ACCOUNT, name, ["account_alert", "account_alert_level"], as_dict=True) or {}
	if (
		level == "Info"
		and current.get("account_alert")
		and LEVELS.get(current.get("account_alert_level"), 0) > LEVELS["Info"]
	):
		return

	frappe.db.set_value(
		ACCOUNT,
		name,
		{"account_alert": text, "account_alert_level": level, "account_alert_at": now_datetime()},
		update_modified=False,
	)


@frappe.whitelist(methods=["POST"])
def dismiss_alert(name: str):
	admin_only()
	frappe.db.set_value(
		ACCOUNT,
		name,
		{"account_alert": None, "account_alert_level": None, "account_alert_at": None},
		update_modified=False,
	)


def mark_verified(verify_token):
	for name in frappe.get_all(ACCOUNT, filters={"webhook_verify_token": verify_token}, pluck="name"):
		frappe.db.set_value(ACCOUNT, name, "webhook_verified_at", now_datetime(), update_modified=False)


def touch(name):
	key = f"onechat:webhook-event:{name}"
	cache = frappe.cache()
	if cache.get_value(key):
		return

	cache.set_value(key, 1, expires_in_sec=EVENT_THROTTLE)
	frappe.db.set_value(ACCOUNT, name, "webhook_last_event_at", now_datetime(), update_modified=False)


def digits(value):
	return "".join(ch for ch in str(value or "") if ch.isdigit())


def find_accounts(waba_id=None, number=None):
	rows = frappe.get_all(ACCOUNT, fields=["name", "business_id", "display_phone_number"])
	wanted = digits(number)
	if wanted:
		matched = [row.name for row in rows if digits(row.display_phone_number) == wanted]
		if matched:
			return matched

	same = [row.name for row in rows if waba_id and row.business_id == str(waba_id)]
	return same if (len(same) == 1 or not wanted) else []


def on_quality_update(value, waba_id=None):
	limit = LIMITS.get(value.get("current_limit"), value.get("current_limit"))
	event = value.get("event")
	messages = {
		"FLAGGED": (
			"Warning",
			_("Quality is low. If it doesn't improve within 7 days, Meta will lower the messaging limit."),
		),
		"UNFLAGGED": ("Info", _("Quality has recovered.")),
		"DOWNGRADE": (
			"Critical",
			_("Meta lowered the messaging limit to {0} because of low quality.").format(limit),
		),
		"UPGRADE": ("Info", _("Meta raised the messaging limit to {0}.").format(limit)),
	}

	for name in find_accounts(waba_id, value.get("display_phone_number")):
		if limit:
			frappe.db.set_value(ACCOUNT, name, "messaging_limit", limit, update_modified=False)
		if event in messages:
			set_alert(name, *messages[event])
		frappe.enqueue(refresh, name=name, enqueue_after_commit=True)


def on_name_update(value, waba_id=None):
	decision = (value.get("decision") or "").upper()
	requested = value.get("requested_verified_name")

	for name in find_accounts(waba_id, value.get("display_phone_number")):
		if decision == "APPROVED":
			frappe.db.set_value(
				ACCOUNT, name, {"name_status": "Approved", "verified_name": requested}, update_modified=False
			)
			set_alert(name, "Info", _("Meta approved the display name {0}.").format(requested))
		elif decision == "REJECTED":
			frappe.db.set_value(ACCOUNT, name, "name_status", "Declined", update_modified=False)
			reason = value.get("rejection_reason")
			text = _("Meta declined the display name {0}.").format(requested)
			set_alert(name, "Warning", f"{text} {reason}" if reason and reason != "NONE" else text)
		elif decision == "DEFERRED":
			frappe.db.set_value(ACCOUNT, name, "name_status", "Pending review", update_modified=False)


def account_event(value):
	event = value.get("event")
	if event == "DISABLED_UPDATE":
		state = (value.get("ban_info") or {}).get("waba_ban_state")
		if state == "REINSTATE":
			return "Info", _("Meta reinstated this WhatsApp Business account.")
		if state == "SCHEDULE_FOR_DISABLE":
			return "Critical", _(
				"Meta scheduled this WhatsApp Business account to be disabled. Check Business Support Home."
			)
		return "Critical", _("Meta disabled this WhatsApp Business account. Messages can't be sent.")
	if event == "ACCOUNT_VIOLATION":
		kind = (value.get("violation_info") or {}).get("violation_type") or ""
		return "Warning", _("Meta reported a policy violation: {0}.").format(
			kind.replace("_", " ").lower() or _("unspecified")
		)
	if event == "ACCOUNT_RESTRICTION":
		kinds = ", ".join(
			(row.get("restriction_type") or "").replace("_", " ").lower()
			for row in value.get("restriction_info") or []
		)
		return "Critical", _("Meta restricted this account: {0}.").format(kinds or _("messaging"))
	if event == "ACCOUNT_DELETED":
		return "Critical", _("This WhatsApp Business account was deleted on Meta.")
	if event == "VERIFIED_ACCOUNT":
		return "Info", _("Meta verified this business.")

	return None


def on_account_update(value, waba_id=None):
	result = account_event(value)
	if not result:
		return

	for name in find_accounts(waba_id, value.get("phone_number")):
		set_alert(name, *result)


@frappe.whitelist()
def profile(name: str):
	admin_only()
	account = frappe.get_doc(ACCOUNT, name)
	if missing(account):
		frappe.throw(_("Add the access token and phone number ID first."))

	data = graph(account, f"{account.phone_id}/whatsapp_business_profile", {"fields": PROFILE_FIELDS})
	row = (data.get("data") or [{}])[0]
	return {
		"about": row.get("about") or "",
		"address": row.get("address") or "",
		"description": row.get("description") or "",
		"email": row.get("email") or "",
		"websites": (row.get("websites") or []) + [""] * (2 - len(row.get("websites") or [])),
		"vertical": row.get("vertical") or "UNDEFINED",
		"profile_picture_url": row.get("profile_picture_url"),
		"verticals": VERTICALS,
		"can_upload": bool(account.app_id),
	}


@frappe.whitelist(methods=["POST"])
def save_profile(name: str, values: JSON):
	admin_only()
	account = frappe.get_doc(ACCOUNT, name)
	values = frappe.parse_json(values) or {}

	payload = {"messaging_product": "whatsapp"}
	for field, limit in PROFILE_LIMITS.items():
		text = (values.get(field) or "").strip()
		if len(text) > limit:
			frappe.throw(_("{0} can be at most {1} characters.").format(_(field.title()), limit))
		payload[field] = text

	if not payload["about"]:
		frappe.throw(_("About can't be empty."))

	websites = [site.strip() for site in values.get("websites") or [] if site and site.strip()][:2]
	for site in websites:
		if not site.startswith(("http://", "https://")):
			frappe.throw(_("Websites must start with http:// or https://"))
	payload["websites"] = websites

	vertical = values.get("vertical") or "UNDEFINED"
	if vertical not in VERTICALS:
		frappe.throw(_("Pick a valid business category."))
	payload["vertical"] = vertical

	graph(account, f"{account.phone_id}/whatsapp_business_profile", method="POST", payload=payload)
	return profile(name)


@frappe.whitelist(methods=["POST"])
def upload_photo(name: str, file_url: str):
	admin_only()
	account = frappe.get_doc(ACCOUNT, name)
	if not account.app_id:
		frappe.throw(_("Add the App ID to this account to upload a profile photo."))

	file = frappe.get_doc("File", {"file_url": file_url})
	content = file.get_content()
	if isinstance(content, str):
		content = content.encode()
	mime = "image/png" if file.file_name.lower().endswith(".png") else "image/jpeg"

	session = graph(
		account,
		f"{account.app_id}/uploads",
		{"file_name": file.file_name, "file_length": len(content), "file_type": mime},
		method="POST",
	)
	response = requests.post(
		f"{account.url}/{account.version}/{session['id']}",
		data=content,
		headers={"Authorization": f"OAuth {token(account)}", "file_offset": "0"},
		timeout=60,
	)
	data = response.json() if response.content else {}
	if response.status_code != 200 or not data.get("h"):
		raise frappe.ValidationError(
			(data.get("error") or {}).get("message") or _("Meta did not accept the photo.")
		)

	graph(
		account,
		f"{account.phone_id}/whatsapp_business_profile",
		method="POST",
		payload={"messaging_product": "whatsapp", "profile_picture_handle": data["h"]},
	)
	frappe.delete_doc("File", file.name, ignore_permissions=True, force=True)
	return profile(name)
