import frappe

from onechat.workspace.webhooks import WEBHOOK, body_of, event_of, onechat_hooks


def execute():
	for row in onechat_hooks():
		frappe.db.set_value(WEBHOOK, row.name, "webhook_json", body_of(event_of(row)), update_modified=False)
