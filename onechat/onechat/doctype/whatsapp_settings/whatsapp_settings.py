from frappe.model.document import Document


class WhatsAppSettings(Document):
	# begin: auto-generated types

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		app_id: DF.Data | None
		auto_add_system_users: DF.Check
		business_id: DF.Data | None
		default_country_code: DF.Int
		enabled: DF.Check
		phone_id: DF.Data | None
		show_onechat_on_desk: DF.Check
		token: DF.Password | None
		url: DF.Data | None
		version: DF.Data | None
		webhook_verify_token: DF.Data | None
	# end: auto-generated types
	pass
