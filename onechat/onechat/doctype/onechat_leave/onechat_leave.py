from frappe.model.document import Document


class OneChatLeave(Document):
	# begin: auto-generated types

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from_date: DF.Date
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		reason: DF.Data | None
		to_date: DF.Date
	# end: auto-generated types

	pass
