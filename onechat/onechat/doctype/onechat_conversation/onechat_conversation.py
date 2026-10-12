from frappe.model.document import Document


class OneChatConversation(Document):
	# begin: auto-generated types

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		agent_replies: DF.Int
		assigned_to: DF.Link | None
		bot_flow: DF.Link | None
		bot_replies: DF.Int
		contact: DF.Link
		first_response_at: DF.Datetime | None
		first_response_by: DF.Link | None
		incoming_count: DF.Int
		opened_at: DF.Datetime | None
		resolution_seconds: DF.Int
		resolved_at: DF.Datetime | None
		resolved_by: DF.Link | None
		response_seconds: DF.Int
		status: DF.Literal["Open", "Resolved"]
		team: DF.Link | None
		whatsapp_account: DF.Link | None
	# end: auto-generated types

	pass
