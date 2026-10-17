import json

import frappe
from frappe import _
from frappe.query_builder.functions import Count

from onechat.workspace.session import require_admin


def validate_flow_graph(graph_json):
	try:
		if isinstance(graph_json, str):
			graph = json.loads(graph_json)
		else:
			graph = graph_json

		errors = []
		warnings = []

		if not isinstance(graph, dict):
			errors.append("Graph must be an object")
			return {"valid": False, "errors": errors, "warnings": warnings}

		if "nodes" not in graph or not isinstance(graph["nodes"], list):
			errors.append("Graph must contain 'nodes' array")

		if "edges" not in graph or not isinstance(graph["edges"], list):
			errors.append("Graph must contain 'edges' array")

		if errors:
			return {"valid": False, "errors": errors, "warnings": warnings}

		trigger_nodes = [
			n for n in graph["nodes"] if n.get("data", {}).get("nodeType", "").endswith("_trigger")
		]
		if not trigger_nodes:
			errors.append("Flow must have at least one trigger node")

		node_ids = {n["id"] for n in graph["nodes"]}
		connected_nodes = set()

		for edge in graph["edges"]:
			if edge["source"] not in node_ids:
				errors.append(f"Edge references non-existent source node: {edge['source']}")
			if edge["target"] not in node_ids:
				errors.append(f"Edge references non-existent target node: {edge['target']}")

			connected_nodes.add(edge["source"])
			connected_nodes.add(edge["target"])

		trigger_ids = {n["id"] for n in trigger_nodes}
		orphaned = node_ids - connected_nodes - trigger_ids

		if orphaned:
			warnings.append(f"Orphaned nodes detected: {', '.join(orphaned)}")

		for node in graph["nodes"]:
			node_type = node.get("data", {}).get("nodeType")
			config = node.get("data", {}).get("config", {})

			if node_type == "whatsapp_send_template":
				if not config.get("to"):
					warnings.append(f"Node {node['id']}: 'to' field is recommended")
				if not config.get("template_name"):
					warnings.append(f"Node {node['id']}: 'template_name' field is recommended")

		return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

	except json.JSONDecodeError as e:
		return {"valid": False, "errors": [f"Invalid JSON: {e!s}"], "warnings": []}
	except Exception as e:
		return {"valid": False, "errors": [str(e)], "warnings": []}


@frappe.whitelist()
def get_flow_statistics():
	require_admin()
	total_flows = frappe.db.count("OneChat Flow")
	active_flows = frappe.db.count("OneChat Flow", {"is_active": 1})

	flow = frappe.qb.DocType("OneChat Flow")
	trigger_types = (
		frappe.qb.from_(flow)
		.select(flow.trigger_type, Count("*").as_("count"))
		.groupby(flow.trigger_type)
		.run(as_dict=True)
	)

	categories = (
		frappe.qb.from_(flow)
		.select(flow.category, Count("*").as_("count"))
		.where(flow.category.isnotnull())
		.groupby(flow.category)
		.run(as_dict=True)
	)

	recent_executions = frappe.db.count(
		"Automation Execution Log", {"start_time": [">=", frappe.utils.add_days(frappe.utils.nowdate(), -7)]}
	)

	total_executions = frappe.db.count("Automation Execution Log")
	successful_executions = frappe.db.count("Automation Execution Log", {"status": "Success"})
	success_rate = (successful_executions / total_executions * 100) if total_executions > 0 else 0

	return {
		"total_flows": total_flows,
		"active_flows": active_flows,
		"inactive_flows": total_flows - active_flows,
		"trigger_types": trigger_types,
		"categories": categories,
		"recent_executions": recent_executions,
		"total_executions": total_executions,
		"success_rate": round(success_rate, 2),
	}
