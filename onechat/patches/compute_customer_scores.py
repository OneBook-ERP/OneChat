import frappe


def execute():
	frappe.enqueue("onechat.inbox.scores.update_all", queue="long", timeout=3600, enqueue_after_commit=True)
