from frappe.model.document import Document


class OneChatSpend(Document):
	# begin: auto-generated types

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		category: DF.Data | None
		cost: DF.Float
		country: DF.Data | None
		currency: DF.Data | None
		date: DF.Date
		pricing_type: DF.Data | None
		volume: DF.Int
		whatsapp_account: DF.Link
	# end: auto-generated types

	pass
