import base64
import hashlib
import hmac
import json
from urllib.parse import urlparse

import frappe
from frappe import _
from frappe.utils import get_url
from frappe.utils.password import get_decrypted_password

from onechat import integrations
from onechat.integrations import connection
from onechat.workspace.session import require_admin

SIGNATURE = "X-Frappe-Webhook-Signature"
RECEIVER = "onechat.integrations.remote_setup.receive"
LEGACY_RECEIVER = "onechat.integrations.erpnext_remote.receive"
EVENTS = ("after_insert", "on_update", "on_submit", "on_cancel", "on_update_after_submit", "on_trash")
ALWAYS = {
	"erpnext": (
		("Payment Request", "on_update_after_submit"),
		("Payment Request", "on_cancel"),
		("Payment Entry", "on_submit"),
		("Customer", "after_insert"),
		("Lead", "after_insert"),
		("Supplier", "after_insert"),
		("Contact", "on_update"),
	),
	"crm": (("CRM Deal", "on_update"), ("CRM Deal", "after_insert"), ("CRM Lead", "after_insert")),
}
ROLES = {
	"erpnext": "Sales User, Accounts User and Stock User",
	"crm": "Sales User and Sales Manager",
}
ROLE = "OneChat Integration"
PERMISSIONS = "frappe.core.page.permission_manager.permission_manager."
ACCESS = {
	"erpnext": {
		"Customer": "rwc",
		"Lead": "rwc",
		"Contact": "rwc",
		"Supplier": "r",
		"Address": "r",
		"Customer Group": "r",
		"Territory": "r",
		"Company": "r",
		"Sales Person": "r",
		"Quotation": "r",
		"Sales Order": "rwc",
		"Sales Invoice": "r",
		"Delivery Note": "r",
		"Payment Entry": "r",
		"Payment Request": "rwcs",
		"Payment Gateway Account": "r",
		"Item": "r",
		"Item Price": "r",
		"Item Group": "r",
		"Brand": "r",
		"Price List": "r",
		"Warehouse": "r",
		"Bin": "r",
		"Selling Settings": "r",
		"Webhook": "rwcd",
	},
	"crm": {
		"CRM Lead": "rwc",
		"CRM Deal": "rwc",
		"CRM Note": "rwc",
		"CRM Task": "rwc",
		"Contact": "rwc",
		"CRM Organization": "r",
		"CRM Deal Status": "r",
		"CRM Lead Status": "r",
		"CRM Lead Source": "r",
		"Webhook": "rwcd",
	},
}
FLAGS = {"w": "write", "c": "create", "d": "delete", "s": "submit"}


def receive_url(key):
	return get_url(f"/api/method/{RECEIVER}?source={key}")


def payload_template(event):
	return (
		'{"doctype": {{ doc.doctype | tojson }}, "name": {{ doc.name | tojson }}, '
		f'"event": "{event}", '
		'"doc": {{ doc.as_json() }}}'
	)


def webhook_secret(row, create=True):
	secret = get_decrypted_password(connection.CONNECTION, row.key, "webhook_secret", raise_exception=False)
	if secret or not create:
		return secret

	secret = frappe.generate_hash(length=40)
	row.update({"webhook_secret": secret})
	return secret


def state(key):
	row = connection.site(key)
	values = row.row()
	api_key, secret = row.credentials()
	return {
		"integration": key,
		"label": row.label,
		"app": row.app,
		"roles": ROLES.get(key, ""),
		"mode": row.mode(),
		"installed_here": row.installed_here(),
		"url": row.base_url(),
		"api_key": api_key or "",
		"has_secret": bool(secret),
		"auth_method": values.get("auth_method") or connection.API_KEY,
		"client_id": values.get("client_id") or "",
		"has_client_secret": bool(
			get_decrypted_password(connection.CONNECTION, key, "client_secret", raise_exception=False)
		),
		"oauth_user": values.get("oauth_user") or "",
		"signed_in": bool(values.get("token_expires_at")),
		"redirect_uri": get_url("/api/method/onechat.integrations.oauth.callback"),
		"status": values.get("status") or "",
		"connected": bool(values.get("connected")),
		"checked_at": values.get("checked_at"),
		"webhooks": values.get("webhooks") or "",
		"last_event_at": values.get("last_event_at"),
		"last_event": values.get("last_event") or "",
		"role": ROLE,
		"role_status": values.get("role_status") or "",
		"access": [{"doctype": doctype, "rights": rights} for doctype, rights in ACCESS.get(key, {}).items()],
		"webhook_url": receive_url(key),
		"ready": row.ready(),
	}


@frappe.whitelist()
def settings(integration: str):
	require_admin()
	return state(integration)


def clean_url(url, label):
	url = (url or "").strip().rstrip("/")
	if url and "://" not in url:
		url = f"https://{url}"
	parsed = urlparse(url)
	if parsed.scheme not in ("http", "https") or not parsed.netloc:
		frappe.throw(_("Enter the {0} site address, for example https://erp.example.com").format(label))
	return f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"


@frappe.whitelist()
def save(
	integration: str,
	mode: str,
	url: str | None = None,
	api_key: str | None = None,
	api_secret: str | None = None,
):
	require_admin()
	row = connection.site(integration)
	if mode not in (connection.THIS_SITE, connection.ANOTHER_SITE):
		frappe.throw(_("Choose where {0} is.").format(row.label))

	values = {"mode": mode}
	if mode == connection.ANOTHER_SITE:
		values.update(
			{
				"url": clean_url(url, row.label),
				"api_key": (api_key or "").strip(),
				"auth_method": connection.API_KEY,
			}
		)
		if api_secret:
			values["api_secret"] = api_secret.strip()
		has_secret = api_secret or row.credentials()[1]
		if not values["api_key"] or not has_secret:
			frappe.throw(_("Enter the API key and secret of a {0} user.").format(row.label))
	elif not row.installed_here():
		frappe.throw(
			_("{0} is not installed on this site. Install it, or choose Another site.").format(row.label)
		)

	row.update(values)
	row.clear_cache()

	if mode == connection.ANOTHER_SITE:
		check(row)
		sync(integration)

	enable(integration)
	return state(integration)


def enable(key):
	off = integrations.disabled()
	if key in off:
		off.discard(key)
		integrations.save_setting("disabled_integrations", json.dumps(sorted(off)))


def check(row):
	try:
		result = row.test()
	except Exception as error:
		row.record_status(_("Not connected: {0}").format(str(error)), False)
		frappe.db.commit()
		raise
	row.record_status(
		_("Connected as {0} · {1} {2}").format(result["user"], row.label, result.get("version") or ""), True
	)
	return result


@frappe.whitelist(methods=["POST"])
def sign_out(integration: str):
	require_admin()
	from onechat.integrations import oauth

	row = connection.site(integration)
	oauth.revoke(row)
	row.record_status(_("Signed out"), False)
	row.clear_cache()
	return state(integration)


def grant(client, doctype, rights):
	current = [
		row
		for row in client.call(f"{PERMISSIONS}get_permissions", doctype=doctype, role=ROLE) or []
		if not row.get("permlevel")
	]
	if not current:
		client.call(f"{PERMISSIONS}add", parent=doctype, role=ROLE, permlevel=0)
		current = [{}]
	for letter, ptype in FLAGS.items():
		if letter in rights and not current[0].get(ptype):
			client.call(f"{PERMISSIONS}update", doctype=doctype, role=ROLE, permlevel=0, ptype=ptype, value=1)
	if not current[0].get("report"):
		client.call(f"{PERMISSIONS}update", doctype=doctype, role=ROLE, permlevel=0, ptype="report", value=1)


@frappe.whitelist(methods=["POST"])
def setup_role(integration: str):
	require_admin()
	row = connection.site(integration)
	if not row.is_remote():
		frappe.throw(_("{0} runs on this site, so no extra role is needed.").format(row.label))

	client = row.client()
	granted, skipped = [], []
	try:
		if not client.get_list("Role", filters={"name": ROLE}, limit=1):
			client.insert({"doctype": "Role", "role_name": ROLE, "desk_access": 1})
		for doctype, rights in ACCESS[integration].items():
			if not client.get_list("DocType", filters={"name": doctype}, limit=1):
				skipped.append(doctype)
				continue
			grant(client, doctype, rights)
			granted.append(doctype)

		user = row.test()["user"]
		if user not in ("Administrator", "Guest"):
			roles = {item.get("role") for item in (client.get_doc("User", user).get("roles") or [])}
			if ROLE not in roles:
				client.insert(
					{
						"doctype": "Has Role",
						"parent": user,
						"parenttype": "User",
						"parentfield": "roles",
						"role": ROLE,
					}
				)
		status = _("{0} role is ready on {1} with access to {2} record types, and {3} has it.").format(
			ROLE, row.label, len(granted), user
		)
		if skipped:
			status += " " + _("Skipped (not installed there): {0}.").format(", ".join(skipped))
	except Exception as error:
		frappe.log_error(title=f"OneChat {row.label} role")
		status = _(
			"Could not set up the {0} role on {1}: {2}. Connect once with a System Manager user, or add the role by hand."
		).format(ROLE, row.label, str(error))

	row.update({"role_status": status})
	return state(integration)


@frappe.whitelist()
def test(integration: str):
	require_admin()
	check(connection.site(integration))
	return state(integration)


def wanted(row):
	from onechat.automation.engine import DOC_EVENT_TRIGGERS, trigger_index

	pairs = set(ALWAYS.get(row.key, ()))
	for trigger in trigger_index():
		doctype, event = trigger["config"].get("doctype"), trigger["config"].get("event")
		if trigger["kind"] not in DOC_EVENT_TRIGGERS or event not in EVENTS:
			continue
		owner = connection.owner_of(doctype)
		if owner and owner.key == row.key:
			pairs.add((doctype, event))
	return pairs


def sync(integration):
	row = connection.site(integration)
	client = row.client()
	secret = webhook_secret(row)
	url = receive_url(integration)
	try:
		existing = client.get_list(
			"Webhook",
			fields=["name", "webhook_doctype", "webhook_docevent"],
			filters={"request_url": url},
			limit=0,
		)
		if integration == "erpnext":
			for legacy in client.get_list(
				"Webhook",
				fields=["name"],
				filters={"request_url": get_url(f"/api/method/{LEGACY_RECEIVER}")},
				limit=0,
			):
				client.call("frappe.client.delete", doctype="Webhook", name=legacy.name)

		have = {(item.webhook_doctype, item.webhook_docevent): item.name for item in existing}
		needed = wanted(row)
		for doctype, event in sorted(needed - set(have)):
			client.insert(
				{
					"doctype": "Webhook",
					"webhook_doctype": doctype,
					"webhook_docevent": event,
					"request_url": url,
					"request_method": "POST",
					"request_structure": "JSON",
					"webhook_json": payload_template(event),
					"webhook_headers": [{"key": "Content-Type", "value": "application/json"}],
					"enable_security": 1,
					"webhook_secret": secret,
					"enabled": 1,
				}
			)
		for pair in set(have) - needed:
			client.call("frappe.client.delete", doctype="Webhook", name=have[pair])
		if needed:
			status = _("{0} {1} events are sent to OneChat: {2}").format(
				len(needed), row.label, ", ".join(f"{doctype} ({event})" for doctype, event in sorted(needed))
			)
		else:
			status = _(
				"No {0} events are needed yet. They are added when a flow starts from a {0} record."
			).format(row.label)
	except Exception as error:
		status = _(
			"Could not set up webhooks on {0}: {1}. Give the API user the System Manager role, or add them by hand."
		).format(row.label, str(error))
		frappe.log_error(title=f"OneChat {row.label} webhooks")

	row.update({"webhooks": status})
	return status


@frappe.whitelist()
def sync_webhooks(integration: str):
	require_admin()
	sync(integration)
	return state(integration)


def schedule_sync():
	for row in connection.remote_sites():
		frappe.enqueue(
			"onechat.integrations.remote_setup.sync",
			queue="short",
			job_id=f"onechat_{row.key}_webhooks",
			deduplicate=True,
			enqueue_after_commit=True,
			integration=row.key,
		)


def verified(row, raw):
	secret = webhook_secret(row, create=False)
	signature = frappe.get_request_header(SIGNATURE) or ""
	if not secret or not signature:
		return False
	expected = base64.b64encode(hmac.new(secret.encode("utf8"), raw, hashlib.sha256).digest()).decode()
	return hmac.compare_digest(signature.strip(), expected)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def receive():
	key = frappe.request.args.get("source") or ""
	raw = frappe.request.get_data() or b""
	row = connection.site(key) if key in connection.APPS else None
	if not row or not row.is_remote() or not verified(row, raw):
		frappe.throw(_("Invalid signature"), frappe.PermissionError)

	try:
		payload = json.loads(raw)
	except ValueError:
		frappe.throw(_("Invalid payload"))

	doctype, name, event = payload.get("doctype"), payload.get("name"), payload.get("event")
	doc = payload.get("doc") or {}
	if isinstance(doc, str):
		doc = json.loads(doc)
	if not (doctype and name and event):
		frappe.throw(_("Invalid payload"))

	frappe.db.set_value(
		connection.CONNECTION,
		key,
		{"last_event_at": frappe.utils.now_datetime(), "last_event": f"{doctype} · {event}"},
		update_modified=False,
	)
	frappe.set_user("Administrator")
	from onechat.automation.engine import doc_event

	doc_event(doctype, name, event, doc)
	if key == "erpnext" and doctype == "Payment Request" and doc.get("status") == "Paid":
		from onechat.integrations.erpnext_commerce import payment_received

		payment_received(frappe._dict(doc))
		from onechat.integrations.payments import alert_request

		alert_request(frappe._dict(doc))
	if key == "erpnext" and doctype == "Payment Request":
		from onechat.integrations.payments import refresh_links

		refresh_links(name)
	if key == "erpnext" and doctype == "Payment Entry" and event == "on_submit":
		from onechat.integrations.erpnext_commerce import remote_entry

		remote_entry(frappe._dict(doc))
	if key == "crm" and doctype == "CRM Deal":
		from onechat.integrations.frappe_crm import remote_deal

		remote_deal(name, doc)
	from onechat.integrations.autolink import remote_event

	remote_event(doctype, name, event, doc)

	return "ok"
