from frappe.model.document import Document


class OneChatConnection(Document):
	# begin: auto-generated types

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		api_key: DF.Data | None
		api_secret: DF.Password | None
		checked_at: DF.Datetime | None
		connected: DF.Check
		integration: DF.Data
		mode: DF.Literal["This site", "Another site"]
		status: DF.SmallText | None
		url: DF.Data | None
		webhook_secret: DF.Password | None
		webhooks: DF.SmallText | None
	# end: auto-generated types

	pass
