import json

import frappe
from frappe import _
from frappe.model.document import Document

from onechat.automation.engine import TRIGGERS, clear_trigger_cache
from onechat.integrations.remote_setup import schedule_sync


class AutomationFlow(Document):
	# begin: auto-generated types

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		category: DF.Literal[
			"Customer Service", "Sales", "Support", "Notifications", "Workflow Automation", "Other"
		]
		created_user: DF.Link | None
		creation_date: DF.Datetime | None
		description: DF.SmallText | None
		flow_name: DF.Data
		graph_json: DF.Code | None
		is_active: DF.Check
		last_modified: DF.Datetime | None
		last_scheduled_run: DF.Datetime | None
		modified_user: DF.Link | None
		reply_timeout_hours: DF.Int
		run_count: DF.Int
		stop_on_agent_reply: DF.Check
		trigger_type: DF.Literal[
			"WhatsApp Incoming", "ERPNext Document Event", "Scheduled", "Manual", "Webhook"
		]

	# end: auto-generated types
	def before_save(self):
		self.last_modified = frappe.utils.now()
		if self.graph_json:
			try:
				graph = json.loads(self.graph_json)
				self.validate_graph_structure(graph)
			except json.JSONDecodeError:
				frappe.throw(_("Invalid JSON in Graph JSON field"))

	def validate_graph_structure(self, graph):
		if not isinstance(graph, dict):
			frappe.throw(_("Graph JSON must be an object"))

		if "nodes" not in graph or not isinstance(graph["nodes"], list):
			frappe.throw(_("Graph JSON must contain 'nodes' array"))

		if "edges" not in graph or not isinstance(graph["edges"], list):
			frappe.throw(_("Graph JSON must contain 'edges' array"))

		trigger_nodes = [node for node in graph["nodes"] if is_trigger(node)]
		if not trigger_nodes and self.is_active:
			frappe.throw(_("Active flow must have at least one trigger node"))
		if self.is_active and (self.has_value_changed("is_active") or self.has_value_changed("graph_json")):
			self.check_steps()

	def check_steps(self):
		from onechat.automation import safety
		from onechat.automation.engine import Graph

		problems = [
			row["message"] for row in safety.check_graph(Graph(self.graph_json)) if row["level"] == "error"
		]
		if problems:
			frappe.throw(
				frappe._("Fix these before turning the flow on:")
				+ "<ul>"
				+ "".join(f"<li>{frappe.utils.escape_html(text)}</li>" for text in problems)
				+ "</ul>",
				title=frappe._("Flow has problems"),
			)

	def autoname(self):
		self.name = self.flow_name

	def before_insert(self):
		self.created_by = frappe.session.user
		self.creation_date = frappe.utils.now()

	def on_update(self):
		clear_trigger_cache()
		schedule_sync()
		if self.is_active and (self.has_value_changed("is_active") or self.has_value_changed("graph_json")):
			from onechat.automation.versions import snapshot

			snapshot(self, self.flags.version_note)

	def on_trash(self):
		clear_trigger_cache()
		schedule_sync()


def is_trigger(node):
	kind = (node.get("data") or {}).get("nodeType") or node.get("type") or ""
	return kind in TRIGGERS or kind.endswith("_trigger")
