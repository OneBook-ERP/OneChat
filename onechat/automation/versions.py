import json

import frappe
from frappe.utils import cint, now_datetime

FLOW = "OneChat Flow"
VERSION = "Automation Flow Version"
DEFINITION = ("graph_json", "trigger_type")


def latest(flow_name):
	return (
		frappe.db.get_value(
			VERSION, {"flow": flow_name}, ["version", "graph_json"], as_dict=True, order_by="version desc"
		)
		or frappe._dict()
	)


def record(flow_name, graph_json, trigger_type, version, user, note=None):
	return frappe.get_doc(
		{
			"doctype": VERSION,
			"flow": flow_name,
			"version": version,
			"graph_json": graph_json,
			"trigger_type": trigger_type,
			"published_by": user,
			"note": note,
		}
	).insert(ignore_permissions=True)


def snapshot(flow, note=None):
	frappe.db.get_value(FLOW, flow.name, "name", for_update=True)
	last = latest(flow.name)
	if not flow.graph_json or last.graph_json == flow.graph_json:
		return
	version = cint(last.version) + 1
	record(flow.name, flow.graph_json, flow.trigger_type, version, frappe.session.user, note)
	flow.db_set(
		{"published_version": version, "published_at": now_datetime(), "published_by": frappe.session.user},
		update_modified=False,
	)


def stage(flow, definition, live):
	if live:
		flow.update(definition)
		flow.draft_json = None
	elif any(definition.get(key) != flow.get(key) for key in definition):
		flow.draft_json = json.dumps(definition)
	else:
		flow.draft_json = None
