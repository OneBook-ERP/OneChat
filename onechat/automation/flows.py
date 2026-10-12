import json
from collections import defaultdict

import frappe
from frappe import _
from frappe.query_builder import Case
from frappe.query_builder.functions import Count
from frappe.utils import add_days, cint, now_datetime

from onechat.api_types import JSON
from onechat.automation import engine
from onechat.automation.versions import DEFINITION, VERSION, stage
from onechat.inbox.visibility import check as check_visible
from onechat.workspace.session import (
	require,
	require_admin,
	require_app_user,
	require_read,
)

FLOW = "Automation Flow"
LOG = "Automation Execution Log"
SESSION = "OneChat Flow Session"
STEP = "Automation Execution Step"
EDITABLE = (
	"flow_name",
	"description",
	"is_active",
	"category",
	"stop_on_agent_reply",
	"reply_timeout_hours",
	"error_message",
	"error_handover",
	"error_team",
	"error_notify",
	"error_pause",
)
WAITING = ("Waiting", "Running")
LEFT = ("Expired", "Stopped")
WHATSAPP_ONLY_STEPS = {"send_template", "send_form", "send_products", "send_to_records"}


@frappe.whitelist()
def get_flows(filters: JSON = None):
	require_admin()

	if isinstance(filters, str):
		filters = json.loads(filters)

	return frappe.get_list(
		FLOW,
		filters=filters or {},
		fields=[
			"name",
			"flow_name",
			"description",
			"is_active",
			"trigger_type",
			"category",
			"run_count",
			"modified",
		],
	)


@frappe.whitelist()
def get_flow(flow_name: str):
	require_admin()
	require_read(FLOW, flow_name)
	return payload(frappe.get_doc(FLOW, flow_name))


def payload(flow):
	data = flow.as_dict()
	data["draft"] = json.loads(flow.draft_json) if flow.get("draft_json") else None
	return data


@frappe.whitelist()
def save_flow(
	flow_name: str | None = None,
	flow_data: JSON = None,
	publish: int | str = 0,
	note: str | None = None,
):
	require_admin()
	require(FLOW, "write" if frappe.db.exists(FLOW, flow_name) else "create")

	if isinstance(flow_data, str):
		flow_data = json.loads(flow_data)
	definition = {key: flow_data[key] for key in DEFINITION if key in flow_data}
	values = {key: flow_data[key] for key in EDITABLE if key in flow_data}

	if flow_name and frappe.db.exists(FLOW, flow_name):
		flow = frappe.get_doc(FLOW, flow_name)
		was_active = cint(flow.is_active)
		flow.update(values)
	else:
		flow = frappe.get_doc({"doctype": FLOW, **values})
		was_active = 0

	stage(flow, definition, live=cint(publish) or not was_active)
	flow.flags.version_note = note
	flow.save()
	return payload(flow)


@frappe.whitelist(methods=["POST"])
def discard_draft(flow_name: str):
	require_admin()
	require(FLOW, "write", flow_name)
	flow = frappe.get_doc(FLOW, flow_name)
	flow.db_set("draft_json", None, update_modified=False)
	return payload(flow)


@frappe.whitelist()
def versions(flow_name: str):
	require_admin()
	require_read(FLOW, flow_name)
	return frappe.get_all(
		VERSION,
		filters={"flow": flow_name},
		fields=["name", "version", "published_by", "creation", "note"],
		order_by="version desc",
		limit_page_length=50,
	)


@frappe.whitelist(methods=["POST"])
def restore_version(flow_name: str, version: str):
	require_admin()
	require(FLOW, "write", flow_name)
	row = frappe.get_doc(VERSION, version)
	if row.flow != flow_name:
		frappe.throw(_("That version belongs to another flow."))
	flow = frappe.get_doc(FLOW, flow_name)
	stage(
		flow,
		{"graph_json": row.graph_json, "trigger_type": row.trigger_type},
		live=not cint(flow.is_active),
	)
	flow.save()
	return payload(flow)


@frappe.whitelist()
def flow_stats(flow_name: str, days: int | str = 30):
	require_admin()
	require_read(FLOW, flow_name)
	since = add_days(now_datetime(), -max(cint(days), 1))
	log = frappe.qb.DocType(LOG)
	step = frappe.qb.DocType(STEP)
	window = (log.flow == flow_name) & (log.creation >= since) & (step.parenttype == LOG)
	nodes = defaultdict(lambda: {"reached": 0, "failed": 0, "waiting": 0, "left": 0})

	for row in (
		frappe.qb.from_(step)
		.join(log)
		.on(step.parent == log.name)
		.select(
			step.node_id,
			Count(log.name).distinct().as_("reached"),
			Count(Case().when(step.status == "Failed", log.name)).distinct().as_("failed"),
		)
		.where(window & step.status.isin(["Success", "Failed"]))
		.groupby(step.node_id)
		.run(as_dict=True)
	):
		nodes[row.node_id].update(reached=cint(row.reached), failed=cint(row.failed))

	session = frappe.qb.DocType(SESSION)
	for row in (
		frappe.qb.from_(session)
		.select(session.current_node, session.status, Count("*").as_("count"))
		.where(
			(session.flow == flow_name)
			& (session.creation >= since)
			& session.status.isin([*WAITING, *LEFT])
			& session.current_node.isnotnull()
		)
		.groupby(session.current_node, session.status)
		.run(as_dict=True)
	):
		key = "waiting" if row.status in WAITING else "left"
		nodes[row.current_node][key] += cint(row.count)

	return {
		"started": frappe.db.count(LOG, {"flow": flow_name, "creation": [">=", since]}),
		"nodes": dict(nodes),
	}


@frappe.whitelist()
def delete_flow(flow_name: str):
	require_admin()
	require(FLOW, "delete")
	for name in frappe.get_all(
		SESSION,
		filters={"flow": flow_name, "status": ["in", engine.OPEN]},
		pluck="name",
	):
		engine.end_session(frappe.get_doc(SESSION, name), "Stopped", _("Flow deleted"))
	frappe.db.delete(SESSION, {"flow": flow_name})
	frappe.db.delete(VERSION, {"flow": flow_name})
	for log in frappe.get_all(LOG, filters={"flow": flow_name}, pluck="name"):
		frappe.delete_doc(LOG, log, ignore_permissions=True)
	frappe.delete_doc(FLOW, flow_name)
	return {"success": True}


@frappe.whitelist()
def execute_flow(flow_name: str, context: JSON = None, contact: str | None = None):
	require_admin()
	if isinstance(context, str):
		context = json.loads(context)

	context = context or {}
	context.setdefault("trigger", "test")
	session = engine.start(flow_name, context, contact=contact or None)
	return {
		"success": session.status != "Failed",
		"session": session.name,
		"status": session.status,
		"log": session.execution_log,
	}


@frappe.whitelist()
def simulate(graph_json: JSON, state: JSON = None, reply: JSON = None):
	require_admin()
	return engine.simulate(
		graph_json,
		frappe.parse_json(state) if state else None,
		frappe.parse_json(reply) if reply else None,
	)


@frappe.whitelist()
def get_execution_logs(flow_name: str | None = None, limit: int | str = 50):
	require_admin()
	filters = {"flow": flow_name} if flow_name else {}
	return frappe.get_list(
		LOG,
		filters=filters,
		fields=[
			"name",
			"flow",
			"run_id",
			"contact",
			"status",
			"start_time",
			"end_time",
			"duration",
		],
		order_by="start_time desc",
		limit=cint(limit) or 50,
	)


@frappe.whitelist()
def get_execution_log(log_name: str):
	require_admin()
	require_read(LOG, log_name)
	return frappe.get_doc(LOG, log_name).as_dict()


@frappe.whitelist()
def manual_flows():
	require_app_user()
	return frappe.get_all(
		FLOW,
		filters={"is_active": 1, "trigger_type": "Manual"},
		fields=["name", "flow_name", "description"],
		order_by="flow_name asc",
	)


@frappe.whitelist(methods=["POST"])
def start_for_contact(flow: str, contact: str):
	require_app_user()
	require("OneChat Message", "create")
	if frappe.db.get_value(FLOW, flow, "trigger_type") != "Manual" or not frappe.db.get_value(
		FLOW, flow, "is_active"
	):
		frappe.throw(_("This flow can't be started from the inbox."))

	session = engine.start_manual(flow, contact)
	if session.status == "Failed":
		frappe.throw(_("The flow could not start: {0}").format(session.stop_reason or _("unknown error")))
	return {"session": session.name, "status": session.status}


@frappe.whitelist(methods=["POST"])
def stop_bot(contact: str):
	require_app_user()
	require("OneChat Contact", "write")
	check_visible(contact)
	engine.stop_contact(contact, _("Stopped by {0}").format(frappe.utils.get_fullname()))


@frappe.whitelist()
def sessions(flow: str | None = None, status: str | None = None, limit: int | str = 20):
	require_admin()
	filters = {}
	if flow:
		filters["flow"] = flow
	if status:
		filters["status"] = status
	return frappe.get_all(
		SESSION,
		filters=filters,
		fields=[
			"name",
			"flow",
			"contact",
			"status",
			"waiting_for",
			"resume_at",
			"stop_reason",
			"execution_log",
			"modified",
		],
		order_by="modified desc",
		limit_page_length=min(cint(limit) or 20, 100),
	)


@frappe.whitelist()
def validate_flow(graph_json: JSON):
	require_admin()
	try:
		graph = engine.Graph(graph_json)
	except (ValueError, KeyError, TypeError) as error:
		return {"valid": False, "errors": [str(error)], "warnings": []}

	errors, warnings = [], []
	if not graph.nodes:
		errors.append(_("Add at least one step."))
	trigger = graph.trigger()
	if not trigger:
		errors.append(_("Add a trigger so the flow knows when to start."))

	kinds = {node_id: engine.Graph.kind(node) for node_id, node in graph.nodes.items()}
	reply_steps = {
		"send_message",
		"send_buttons",
		"send_list",
		"ask_question",
		"send_form",
	}
	trigger_kind = kinds.get(trigger)
	if trigger_kind in (*engine.DOC_EVENT_TRIGGERS, "scheduled_trigger"):
		first = graph.following(trigger, None, frappe._dict(legacy_condition=lambda condition: True))
		if any(kinds.get(node_id) in reply_steps for node_id in first):
			warnings.append(
				_(
					"This flow starts without a customer message, so WhatsApp only delivers templates at first. Start with Send template, then use buttons or questions."
				)
			)

	trigger_config = engine.Graph.config(graph.nodes[trigger]) if trigger else {}
	instagram_only = trigger_kind == "comment_received"
	if instagram_only or (trigger_config.get("channel") or "WhatsApp") != "WhatsApp":
		blocked = sorted({kind for kind in kinds.values() if kind in WHATSAPP_ONLY_STEPS})
		if blocked:
			errors.append(
				_(
					"These steps only work on WhatsApp, so remove them or set the trigger to WhatsApp: {0}"
				).format(", ".join(blocked))
			)

	from onechat.automation import safety

	issues = safety.check_graph(graph)
	return {
		"valid": not errors and not any(row["level"] == "error" for row in issues),
		"errors": errors,
		"warnings": warnings,
		"issues": issues,
	}
