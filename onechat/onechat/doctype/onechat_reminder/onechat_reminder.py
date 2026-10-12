from frappe.model.document import Document


class OneChatReminder(Document):
	# begin: auto-generated types

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		contact: DF.Link
		note: DF.SmallText | None
		only_if_no_reply: DF.Check
		remind_at: DF.Datetime
		sent_at: DF.Datetime | None
		status: DF.Literal["Pending", "Sent", "Skipped", "Cancelled"]
		user: DF.Link
	# end: auto-generated types

	pass
