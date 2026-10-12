from frappe.model.document import Document


class WhatsAppButton(Document):
	# begin: auto-generated types

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		button_label: DF.Data
		button_type: DF.Literal["Quick Reply", "Call Phone", "Visit Website", "Flow"]
		example_url: DF.Data | None
		flow_id: DF.Data | None
		is_active: DF.Check
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		phone_number: DF.Data | None
		sequence: DF.Int
		url_type: DF.Literal["Static", "Dynamic"]
		website_url: DF.Data | None
		whatsapp_flow: DF.Link | None
	# end: auto-generated types
	pass
