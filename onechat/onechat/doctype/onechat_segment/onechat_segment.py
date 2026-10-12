from frappe.model.document import Document


class OneChatSegment(Document):
	# begin: auto-generated types

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		counted_at: DF.Datetime | None
		description: DF.SmallText | None
		match: DF.Literal["all", "any"]
		member_count: DF.Int
		rules: DF.Code | None
		segment_name: DF.Data
	# end: auto-generated types

	pass
