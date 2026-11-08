import frappe
from frappe import _
from frappe.utils import cint


def assistant_spec():
	return {
		"name": "assistant",
		"label": _("AI Assistant"),
		"icon": "lucide-sparkles",
		"category": _("AI"),
		"description": _(
			"Agents ask about a customer and get answers from ERPNext and CRM, or a drafted reply, using Claude, OpenAI or another AI provider."
		),
		"features": [
			_("Answers like what a customer owes or where their order is"),
			_("Drafts replies agents can insert with one click"),
			_("Creates or updates records only after the agent confirms"),
			_("Access by role; code, database queries and deleting are never allowed"),
		],
		"ready": "onechat.integrations.extras.always",
		"active": "onechat.integrations.extras.assistant_active",
		"where": "onechat.integrations.extras.assistant_where",
		"sites_help": _(
			"The assistant reads your ERPNext and CRM data wherever they are connected. On this site each agent's own permissions apply. On another site it uses the agent's own sign-in when agents sign in, otherwise the connection's login."
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
	from onechat.integrations import api, connection

	out, local = [], False
	for key in connection.APPS:
		site = connection.site(key)
		if site.is_remote() and site.ready():
			out.append(api.app_site(key))
		elif not site.is_remote() and site.installed_here() and not local:
			out.append({**api.app_site(key), "auth": _("Each agent")})
			local = True
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
