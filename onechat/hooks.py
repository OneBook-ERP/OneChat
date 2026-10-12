app_name = "onechat"
app_title = "OneChat"
app_publisher = "Leo Daniel A"
app_description = "A comprehensive WhatsApp business automation platform"
app_email = "daniel@onebook.app"
app_license = "AGPL-3.0"

add_to_apps_screen = [
	{
		"name": "onechat",
		"logo": "/assets/onechat/images/onechat-logo.svg",
		"title": "OneChat",
		"route": "/onechat",
		"has_permission": "onechat.workspace.session.can_use_app",
	}
]

export_python_type_annotations = True

onechat_integrations = [
	"onechat.integrations.erpnext.spec",
	"onechat.integrations.frappe_crm.spec",
	"onechat.integrations.extras.payments_spec",
	"onechat.integrations.extras.assistant_spec",
]

before_install = "onechat.setup.install.before_install"

before_uninstall = "onechat.setup.install.before_uninstall"

app_include_js = "onechat_desk.bundle.js"
app_include_css = "onechat_desk.bundle.css"

boot_session = "onechat.workspace.desk.boot_session"

permission_query_conditions = {
	"OneChat Contact": "onechat.inbox.visibility.contact_query",
	"OneChat Message": "onechat.inbox.visibility.message_query",
	"OneChat Note": "onechat.inbox.visibility.note_query",
	"WhatsApp Templates": "onechat.workspace.numbers.template_query",
	"WhatsApp Flow": "onechat.workspace.numbers.form_query",
	"OneChat Chat Link": "onechat.workspace.numbers.chat_link_query",
	"Bulk WhatsApp Message": "onechat.workspace.numbers.broadcast_query",
}

has_permission = {
	"OneChat Contact": "onechat.inbox.visibility.contact_permission",
	"OneChat Message": "onechat.inbox.visibility.message_permission",
	"OneChat Note": "onechat.inbox.visibility.note_permission",
}


doc_events = {
	"*": {
		"before_insert": [
			"onechat.utils.run_server_script_for_doc_event",
			"onechat.automation.engine.on_doc_event",
		],
		"after_insert": [
			"onechat.utils.run_server_script_for_doc_event",
			"onechat.automation.engine.on_doc_event",
		],
		"before_validate": [
			"onechat.utils.run_server_script_for_doc_event",
			"onechat.automation.engine.on_doc_event",
		],
		"validate": [
			"onechat.utils.run_server_script_for_doc_event",
			"onechat.automation.engine.on_doc_event",
		],
		"on_update": [
			"onechat.utils.run_server_script_for_doc_event",
			"onechat.automation.engine.on_doc_event",
		],
		"before_submit": [
			"onechat.utils.run_server_script_for_doc_event",
			"onechat.automation.engine.on_doc_event",
		],
		"on_submit": [
			"onechat.utils.run_server_script_for_doc_event",
			"onechat.automation.engine.on_doc_event",
		],
		"before_cancel": [
			"onechat.utils.run_server_script_for_doc_event",
			"onechat.automation.engine.on_doc_event",
		],
		"on_cancel": [
			"onechat.utils.run_server_script_for_doc_event",
			"onechat.automation.engine.on_doc_event",
		],
		"on_trash": [
			"onechat.utils.run_server_script_for_doc_event",
			"onechat.automation.engine.on_doc_event",
		],
		"after_delete": [
			"onechat.utils.run_server_script_for_doc_event",
			"onechat.automation.engine.on_doc_event",
		],
		"before_update_after_submit": [
			"onechat.utils.run_server_script_for_doc_event",
			"onechat.automation.engine.on_doc_event",
		],
		"on_update_after_submit": [
			"onechat.utils.run_server_script_for_doc_event",
			"onechat.automation.engine.on_doc_event",
		],
	},
	"OneChat Message": {
		"after_insert": [
			"onechat.inbox.accounts.on_message",
			"onechat.inbox.conversations.on_message",
			"onechat.inbox.consent.on_message",
			"onechat.automation.engine.on_message",
			"onechat.inbox.auto_reply.on_message",
			"onechat.inbox.routing.on_message",
			"onechat.campaigns.chat_links.on_message",
			"onechat.inbox.read_receipts.on_message",
			"onechat.integrations.crm_bridge.on_message",
		],
		"on_update": [
			"onechat.inbox.conversations.on_status",
			"onechat.integrations.crm_bridge.on_status",
		],
	},
	"OneChat Contact": {"after_insert": "onechat.inbox.duplicates.on_contact_insert"},
	"OneChat Note": {
		"on_update": "onechat.inbox.conversations.note_saved",
		"on_trash": "onechat.inbox.conversations.note_deleted",
	},
	"CRM Deal": {
		"on_update": "onechat.integrations.frappe_crm.deal_update",
		"after_insert": "onechat.integrations.autolink.record_created",
	},
	"CRM Lead": {
		"after_insert": "onechat.integrations.autolink.record_created",
	},
	"Customer": {
		"after_insert": "onechat.integrations.autolink.record_created",
	},
	"Lead": {
		"after_insert": "onechat.integrations.autolink.record_created",
	},
	"Supplier": {
		"after_insert": "onechat.integrations.autolink.record_created",
	},
	"Contact": {
		"on_update": "onechat.integrations.autolink.record_created",
	},
	"Delivery Note": {
		"on_submit": "onechat.whatsapp.pay.delivered",
	},
	"Payment Entry": {
		"on_submit": "onechat.integrations.erpnext_commerce.entry_submitted",
	},
	"Payment Request": {
		"on_payment_authorized": "onechat.integrations.erpnext_commerce.payment_update",
		"on_update_after_submit": "onechat.integrations.erpnext_commerce.payment_update",
		"on_cancel": "onechat.integrations.payments.request_changed",
	},
	"User": {
		"after_insert": "onechat.onechat.doctype.onechat_user.onechat_user.add_user_to_onechat",
		"on_update": "onechat.onechat.doctype.onechat_user.onechat_user.add_user_to_onechat",
		"on_trash": "onechat.onechat.doctype.onechat_user.onechat_user.remove_user_from_onechat",
	},
}


scheduler_events = {
	"cron": {
		"* * * * *": [
			"onechat.automation.engine.tick",
			"onechat.inbox.followups.run",
			"onechat.workspace.shifts.run",
			"onechat.campaigns.ab_test.run",
			"onechat.inbox.service.run",
		],
		"*/15 * * * *": [
			"onechat.whatsapp.pay.retry_pending",
		],
	},
	"all": [
		"onechat.utils.trigger_whatsapp_notifications_all",
		"onechat.campaigns.broadcasts.send_due_broadcasts",
	],
	"hourly": ["onechat.assistant.fac.cleanup_tokens", "onechat.utils.trigger_whatsapp_notifications_hourly"],
	"hourly_long": [
		"onechat.utils.trigger_whatsapp_notifications_hourly_long",
		"onechat.insights.costs.sync_all",
	],
	"daily": [
		"onechat.workspace.retention.run",
		"onechat.assistant.api.cleanup_history",
		"onechat.whatsapp.accounts.check_all",
		"onechat.instagram.accounts.refresh_tokens",
		"onechat.whatsapp.webhook.purge_logs",
		"onechat.utils.trigger_whatsapp_notifications_daily",
		"onechat.onechat.doctype.whatsapp_notification.whatsapp_notification.trigger_notifications",
	],
	"daily_long": [
		"onechat.utils.trigger_whatsapp_notifications_daily_long",
		"onechat.inbox.scores.update_all",
		"onechat.inbox.duplicates.merge_all",
		"onechat.integrations.erpnext_commerce.nightly_sync",
	],
	"weekly": [
		"onechat.utils.trigger_whatsapp_notifications_weekly",
	],
	"weekly_long": [
		"onechat.utils.trigger_whatsapp_notifications_weekly_long",
	],
	"monthly": [
		"onechat.utils.trigger_whatsapp_notifications_monthly",
	],
	"monthly_long": [
		"onechat.utils.trigger_whatsapp_notifications_monthly_long",
	],
}

website_route_rules = [
	{"from_route": "/onechat/<path:app_path>", "to_route": "onechat"},
	{"from_route": "/c/<code>", "to_route": "onechat_click"},
]

BRIDGE = "onechat.integrations.crm_bridge"
override_whitelisted_methods = {
	**{
		f"crm.api.whatsapp.{method}": f"{BRIDGE}.{method}"
		for method in (
			"is_whatsapp_installed",
			"is_whatsapp_enabled",
			"get_whatsapp_messages",
			"create_whatsapp_message",
			"send_whatsapp_template",
			"react_on_whatsapp_message",
		)
	},
	**{
		f"whatsapp.whatsapp.api.messages.{method}": f"{BRIDGE}.{method}"
		for method in ("get_messages", "send_message", "react_to_message", "send_template")
	},
	"whatsapp.whatsapp.doctype.wa_template.wa_template.get_sendable_templates": f"{BRIDGE}.get_sendable_templates",
}
