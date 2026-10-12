import frappe
from frappe import _
from frappe.utils import cint


def assistant_spec():
	return {
		"name": "assistant",
		"label": _("Assistant (FAC)"),
		"icon": "lucide-sparkles",
		"logo": "/assets/onechat/images/integrations/fac.svg",
		"category": _("AI"),
		"description": _(
			"Agents ask about a customer and get answers from ERPNext and CRM, or a drafted reply, using Frappe Assistant Core with Claude or OpenAI."
		),
		"features": [
			_("Answers like what a customer owes or where their order is"),
			_("Drafts replies agents can insert with one click"),
			_("Creates or updates records only after the agent confirms"),
			_("Access by role; code, database queries and deleting are never allowed"),
		],
		"docs_url": "https://github.com/buildswithpaul/Frappe_Assistant_Core",
		"ready": "onechat.integrations.extras.always",
		"active": "onechat.integrations.extras.assistant_active",
		"where": "onechat.integrations.extras.assistant_where",
		"sites_help": _(
			"FAC reads the data of the site it is installed on. Install it on the site that has your ERPNext or CRM. On this site each agent's own permissions apply. On another site OneChat uses that connection's Sign in (OAuth), so FAC acts as the admin who signed in."
		),
		"setup": "assistant",
	}


def payments_spec():
	return {
		"name": "payments",
		"label": _("Payments"),
		"icon": "lucide-credit-card",
		"logo": "/assets/onechat/images/integrations/payments.svg",
		"category": _("Payments"),
		"description": _(
			"Send secure payment links for invoices and orders from chats and flows, through Frappe Payments gateways like Razorpay or Stripe, with automatic receipts."
		),
		"features": [
			_("Full balance or advance payment links"),
			_("Falls back to your template when the chat is closed"),
			_("Receipt on WhatsApp when the gateway confirms"),
			_("Send payment link step in flows"),
		],
		"ready": "onechat.integrations.extras.erpnext_available",
		"active": "onechat.integrations.extras.payments_active",
		"where": "onechat.integrations.extras.payments_where",
		"sites_help": _(
			"Payments follow ERPNext: the payment request and the gateway live on the ERPNext site. OneChat creates the link there, and that site's webhook tells OneChat when it is paid so the receipt goes out."
		),
		"setup": "payments",
	}


def assistant_where():
	from onechat.assistant import fac
	from onechat.integrations import api, connection

	out = []
	if fac.local_installed():
		out.append(
			{
				**api.app_site("erpnext"),
				"label": frappe.local.site,
				"url": "",
				"remote": False,
				"auth": _("Each agent"),
				"user": "",
				"ready": True,
			}
		)
	for row in connection.remote_sites():
		if row.uses_oauth() and fac.remote_has_fac(row):
			out.append(api.app_site(row.key))
	return out


def payments_where():
	from onechat.integrations import api
	from onechat.integrations.payments import gateway_accounts

	site = api.app_site("erpnext")
	gateways = [row.get("payment_gateway") for row in gateway_accounts() if row.get("payment_gateway")]
	return [{**site, "detail": ", ".join(sorted(set(gateways))) or _("No gateway yet")}]


def always():
	return True


def assistant_active():
	return bool(cint(frappe.get_cached_doc("OneChat Settings").get("assistant_enabled")))


def erpnext_available():
	from onechat.integrations import connection

	site = connection.site("erpnext")
	return site.ready()


def payments_active():
	from onechat.integrations.payments import gateway_ready

	return gateway_ready()
