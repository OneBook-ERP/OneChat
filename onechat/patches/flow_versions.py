import frappe

from onechat.automation.versions import FLOW, VERSION, record


def execute():
	for flow in frappe.get_all(
		FLOW, filters={"is_active": 1}, fields=["name", "graph_json", "trigger_type", "owner"]
	):
		if not flow.graph_json or frappe.db.exists(VERSION, {"flow": flow.name}):
			continue
		record(flow.name, flow.graph_json, flow.trigger_type, 1, flow.owner)
		frappe.db.set_value(FLOW, flow.name, "published_version", 1, update_modified=False)
