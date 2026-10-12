import os

import frappe
from frappe import _
from frappe.utils import add_to_date, cint, get_datetime, now_datetime, pretty_date
from frappe.utils.password import get_decrypted_password

from onechat.workspace.session import require_admin

OK = "ok"
WARN = "warn"
FAIL = "error"
OFF = "off"
ACCOUNT = "OneChat Account"
TEMPLATE = "WhatsApp Templates"
SETTINGS = "OneChat Settings"
HEARTBEAT = "onechat.inbox.followups.run"
HEARTBEAT_MINUTES = 10
WEBHOOK_QUIET_HOURS = 24
ERROR_HOURS = 24
APPROVED = "APPROVED"


def row(key, group, title, status, detail, fix=None, link=None):
	return {
		"key": key,
		"group": group,
		"title": title,
		"status": status,
		"detail": detail,
		"fix": fix,
		"link": link,
	}


def ago(value):
	return pretty_date(value) if value else _("never")


def system():
	from frappe.utils.scheduler import is_scheduler_disabled, is_scheduler_inactive

	group = _("System")
	out = []
	job = (
		frappe.db.get_value(
			"Scheduled Job Type", {"method": HEARTBEAT}, ["last_execution", "stopped"], as_dict=True
		)
		or {}
	)
	last = job.get("last_execution")
	fresh = last and get_datetime(last) > add_to_date(now_datetime(), minutes=-HEARTBEAT_MINUTES)
	if is_scheduler_disabled():
		out.append(
			row(
				"scheduler",
				group,
				_("Scheduler"),
				FAIL,
				_("The scheduler is turned off for this site."),
				_("Run: bench --site {0} enable-scheduler").format(frappe.local.site),
			)
		)
	elif is_scheduler_inactive() or cint(job.get("stopped")) or not fresh:
		out.append(
			row(
				"scheduler",
				group,
				_("Scheduler"),
				FAIL,
				_(
					"OneChat's every-minute job last ran {0}. Reminders, flows, payment checks and broadcasts are not running."
				).format(ago(last)),
				_(
					"Check that the scheduler and bench workers are running (bench doctor), then bench restart."
				),
			)
		)
	else:
		out.append(
			row(
				"scheduler", group, _("Scheduler"), OK, _("Jobs are running. Last run {0}.").format(ago(last))
			)
		)

	try:
		from frappe.utils.background_jobs import get_workers

		workers = len(get_workers())
	except Exception:
		workers = None
	if workers:
		out.append(
			row("workers", group, _("Background workers"), OK, _("{0} workers are running.").format(workers))
		)
	else:
		out.append(
			row(
				"workers",
				group,
				_("Background workers"),
				FAIL if workers == 0 else WARN,
				_("No background workers found.") if workers == 0 else _("Could not reach the job queue."),
				_("Start the workers with bench restart, or check Redis."),
			)
		)

	handlers = os.path.exists(os.path.join(frappe.get_app_path("onechat"), "..", "realtime", "handlers.js"))
	out.append(
		row(
			"handlers",
			group,
			_("Live update handlers"),
			OK if handlers else FAIL,
			_("The typing indicator handlers are installed.")
			if handlers
			else _(
				"realtime/handlers.js is missing from the OneChat app folder, so typing indicators won't show."
			),
			None
			if handlers
			else _("Update the OneChat app, then restart the socket server with bench restart."),
		)
	)

	since = add_to_date(now_datetime(), hours=-ERROR_HOURS)
	errors = frappe.db.count("Error Log", {"creation": [">=", since], "method": ["like", "%OneChat%"]})
	out.append(
		row(
			"errors",
			group,
			_("OneChat errors"),
			OK if not errors else WARN,
			_("No OneChat errors in the last 24 hours.")
			if not errors
			else _("{0} OneChat errors in the last 24 hours.").format(errors),
			None if not errors else _("Open the Error Log to see what failed."),
			None if not errors else "/app/error-log?method=%5B%22like%22%2C%22%25OneChat%25%22%5D",
		)
	)
	return out


def whatsapp():
	group = _("Accounts")
	accounts = frappe.get_all(
		ACCOUNT,
		filters={"status": "Active"},
		fields=[
			"name",
			"account_name",
			"connection_status",
			"account_alert",
			"account_alert_level",
			"webhook_verified_at",
			"webhook_last_event_at",
			"last_checked_at",
		],
	)
	if not accounts:
		return [
			row(
				"accounts",
				group,
				_("Accounts"),
				FAIL,
				_("No active account."),
				_("Add one under Settings → Accounts."),
				"settings:accounts",
			)
		]
	out = []
	quiet = add_to_date(now_datetime(), hours=-WEBHOOK_QUIET_HOURS)
	for account in accounts:
		label = account.account_name or account.name
		if account.connection_status == "Error":
			out.append(
				row(
					f"account:{account.name}",
					group,
					label,
					FAIL,
					account.account_alert or _("Meta rejected the last check."),
					_("Open the account and check its token."),
					"settings:accounts",
				)
			)
		else:
			out.append(
				row(
					f"account:{account.name}",
					group,
					label,
					OK,
					_("Connected. Checked {0}.").format(ago(account.last_checked_at)),
				)
			)
		last = account.webhook_last_event_at
		if not last and not account.webhook_verified_at:
			status, detail, fix = (
				FAIL,
				_("Meta has never called the webhook."),
				_("Set the callback URL and verify token in Meta's app dashboard and subscribe to messages."),
			)
		elif not last:
			status, detail, fix = (
				WARN,
				_("The webhook is verified, but no events have arrived yet."),
				_("Subscribe the app to the messages field in Meta's dashboard."),
			)
		elif get_datetime(last) < quiet:
			status, detail, fix = (
				WARN,
				_(
					"Last event from Meta {0}. If customers wrote since then, the webhook may have stopped."
				).format(ago(last)),
				_("Check the webhook subscription in Meta's dashboard."),
			)
		else:
			status, detail, fix = OK, _("Receiving events. Last one {0}.").format(ago(last)), None
		out.append(
			row(
				f"webhook:{account.name}",
				group,
				_("{0} webhook").format(label),
				status,
				detail,
				fix,
				None if status == OK else "settings:accounts",
			)
		)
		if not get_decrypted_password(ACCOUNT, account.name, "app_secret", raise_exception=False):
			out.append(
				row(
					f"secret:{account.name}",
					group,
					_("{0} app secret").format(label),
					FAIL,
					_("No app secret, so Meta's webhook calls are rejected and no messages arrive."),
					_("Add the app secret from Meta app → App settings → Basic."),
					"settings:accounts",
				)
			)
	return out


def connections():
	from onechat.integrations import connection
	from onechat.integrations.remote_setup import receive_url, wanted

	group = _("Connected sites")
	out = []
	for key in connection.APPS:
		site = connection.site(key)
		if not site.is_remote():
			continue
		values = site.row()
		label = site.label
		if not site.ready():
			out.append(
				row(
					f"site:{key}",
					group,
					label,
					FAIL,
					_("Sign-in details are missing."),
					_("Open the integration and connect again."),
					"settings:integrations",
				)
			)
			continue
		try:
			site.test()
			out.append(
				row(
					f"site:{key}",
					group,
					label,
					OK,
					_("Reachable. Last event {0}.").format(ago(values.get("last_event_at"))),
				)
			)
		except Exception as error:
			out.append(
				row(
					f"site:{key}",
					group,
					label,
					FAIL,
					_("Can't reach {0}: {1}").format(label, str(error)),
					_("Check the URL and sign-in in Integrations."),
					"settings:integrations",
				)
			)
			continue
		try:
			have = {
				(item.get("webhook_doctype"), item.get("webhook_docevent"))
				for item in site.client().get_list(
					"Webhook",
					fields=["webhook_doctype", "webhook_docevent"],
					filters={"request_url": receive_url(key), "enabled": 1},
					limit=0,
				)
			}
			missing = sorted(wanted(site) - have)
		except Exception as error:
			out.append(
				row(
					f"hooks:{key}",
					group,
					_("{0} events").format(label),
					WARN,
					_("Couldn't read webhooks on {0}: {1}").format(label, str(error)),
					_("Give the API user permission to read Webhook."),
				)
			)
			continue
		if missing:
			out.append(
				row(
					f"hooks:{key}",
					group,
					_("{0} events").format(label),
					FAIL,
					_("Not registered: {0}").format(
						", ".join(f"{doctype} ({event})" for doctype, event in missing)
					),
					_("Open the integration and save the connection again to register them."),
					"settings:integrations",
				)
			)
		else:
			out.append(
				row(
					f"hooks:{key}",
					group,
					_("{0} events").format(label),
					OK,
					_("All events OneChat needs are registered."),
				)
			)
	return out


def template_row(key, group, title, name, missing_status, missing_detail):
	if not name:
		return row(
			key,
			group,
			title,
			missing_status,
			missing_detail,
			_("Choose an approved template under Payments."),
			"settings:integrations",
		)
	value = frappe.db.get_value(TEMPLATE, name, ["template_name", "status"], as_dict=True)
	if not value:
		return row(
			key,
			group,
			title,
			FAIL,
			_("The chosen template no longer exists."),
			_("Choose another one under Payments."),
			"settings:integrations",
		)
	if (value.status or "").upper() != APPROVED:
		return row(
			key,
			group,
			title,
			FAIL,
			_("{0} is {1}, not approved.").format(
				value.template_name or name, (value.status or _("pending")).lower()
			),
			_("Wait for Meta's approval or choose another template."),
			"settings:integrations",
		)
	return row(key, group, title, OK, _("{0} is approved.").format(value.template_name or name))


def payments():
	from onechat.integrations.erpnext_commerce import enabled

	if not enabled():
		return []
	from onechat.integrations.payments import gateway_ready

	group = _("Payments")
	settings = frappe.get_cached_doc(SETTINGS)
	out = []
	try:
		ready = gateway_ready()
	except Exception:
		ready = False
	out.append(
		row(
			"gateway",
			group,
			_("Payment gateway"),
			OK if ready else FAIL,
			_("A default Payment Gateway Account is set in ERPNext.")
			if ready
			else _("No default Payment Gateway Account in ERPNext, so payment links can't be created."),
			None if ready else _("Create one in ERPNext and tick Is Default."),
			None if ready else "/app/payment-gateway-account",
		)
	)
	out.append(
		template_row(
			"payment_template",
			group,
			_("Payment link template"),
			settings.get("payment_template"),
			WARN,
			_("Not set. Payment links only reach customers who wrote in the last 24 hours."),
		)
	)
	receipts = cint(settings.get("payment_receipts") if settings.get("payment_receipts") is not None else 1)
	if receipts:
		out.append(
			template_row(
				"receipt_template",
				group,
				_("Receipt template"),
				settings.get("receipt_template"),
				WARN,
				_("Not set. Receipts are skipped when the customer hasn't written in the last 24 hours."),
			)
		)
	else:
		out.append(
			row("receipt_template", group, _("Receipt template"), OFF, _("Payment receipts are turned off."))
		)
	return out


def assistant():
	settings = frappe.get_cached_doc(SETTINGS)
	if not cint(settings.get("assistant_enabled")):
		return []
	from onechat.assistant.api import key_of
	from onechat.assistant.fac import installed

	group = _("Assistant")
	key = bool(key_of(settings))
	fac = installed()
	if key and fac:
		return [
			row(
				"assistant",
				group,
				_("Assistant"),
				OK,
				_("An API key is set and Frappe Assistant Core is available."),
			)
		]
	problems = [
		text
		for ok, text in (
			(key, _("no API key")),
			(fac, _("Frappe Assistant Core isn't installed or connected")),
		)
		if not ok
	]
	return [
		row(
			"assistant",
			group,
			_("Assistant"),
			FAIL,
			_("Not ready: {0}.").format(", ".join(problems)),
			_("Finish setup under Assistant."),
			"settings:integrations",
		)
	]


def crm_whatsapp():
	if "whatsapp" not in frappe.get_installed_apps() or not frappe.db.table_exists("WA Account"):
		return []
	group = _("Frappe CRM")
	title = _("CRM WhatsApp app")
	count = frappe.db.count("WA Account")
	if count:
		return [
			row(
				"crm_whatsapp",
				group,
				title,
				WARN,
				_(
					"Frappe's WhatsApp app has {0} account(s). OneChat already serves CRM's WhatsApp tab, so messages sent through that app skip the OneChat inbox."
				).format(count),
				_("Remove the accounts from CRM Settings, WhatsApp."),
			)
		]
	return [row("crm_whatsapp", group, title, OK, _("CRM's WhatsApp tab uses OneChat."))]


SECTIONS = (system, whatsapp, connections, payments, assistant, crm_whatsapp)


@frappe.whitelist()
def report():
	require_admin()
	checks = []
	for section in SECTIONS:
		try:
			checks += section()
		except Exception as error:
			frappe.log_error(title=f"OneChat health: {section.__name__}")
			checks.append(
				row(
					section.__name__,
					_("Health"),
					section.__name__.capitalize(),
					WARN,
					_("This check failed to run: {0}").format(str(error)),
				)
			)
	return {"checks": checks, "generated_at": str(now_datetime())}
