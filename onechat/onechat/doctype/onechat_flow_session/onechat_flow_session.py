from frappe.model.document import Document


class OneChatFlowSession(Document):
	# begin: auto-generated types

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		contact: DF.Link | None
		context_json: DF.Code | None
		current_node: DF.Data | None
		execution_log: DF.Link | None
		flow: DF.Link
		phone: DF.Data | None
		resume_at: DF.Datetime | None
		status: DF.Literal["Running", "Waiting", "Completed", "Stopped", "Failed", "Expired"]
		stop_reason: DF.Data | None
		waiting_for: DF.Literal["", "Reply", "Form", "Timer"]
		whatsapp_account: DF.Link | None
	# end: auto-generated types

	pass
