import frappe
from frappe.model.document import Document
from frappe.utils import get_datetime, now, time_diff_in_seconds


class AutomationExecutionLog(Document):
	# begin: auto-generated types

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from onechat.onechat.doctype.automation_execution_step.automation_execution_step import (
			AutomationExecutionStep,
		)

		context_json: DF.Code | None
		duration: DF.Float
		end_time: DF.Datetime | None
		error_message: DF.Code | None
		error_node_id: DF.Data | None
		execution_steps: DF.Table[AutomationExecutionStep]
		flow: DF.Link
		run_id: DF.Data
		start_time: DF.Datetime | None
		status: DF.Literal["Running", "Success", "Failed", "Partially Failed", "Cancelled"]
		trigger_data: DF.Code | None

	# end: auto-generated types
	def before_save(self):
		if self.start_time and self.end_time:
			start = get_datetime(self.start_time)
			end = get_datetime(self.end_time)
			self.duration = time_diff_in_seconds(end, start)

	def add_step(self, node_id, node_type, status, output=None, error=None):
		self.append(
			"execution_steps",
			{
				"node_id": node_id,
				"node_type": node_type,
				"status": status,
				"output": output,
				"error": error,
				"timestamp": now(),
			},
		)
		self.save()

	def mark_success(self):
		self.status = "Success"
		self.end_time = now()
		self.save()

	def mark_failed(self, error_message, error_node_id=None):
		self.status = "Failed"
		self.end_time = now()
		self.error_message = error_message
		if error_node_id:
			self.error_node_id = error_node_id
		self.save()
