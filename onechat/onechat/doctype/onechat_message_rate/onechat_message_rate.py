import frappe
from frappe import _
from frappe.model.document import Document


class OneChatMessageRate(Document):
	# begin: auto-generated types

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		category: DF.Literal["marketing", "utility", "authentication", "service"]
		country: DF.Data
		currency: DF.Data | None
		rate: DF.Float
		source: DF.Literal["Manual", "Meta"]
	# end: auto-generated types

	def validate(self):
		self.country = (self.country or "").strip().upper() or "*"
		if self.rate < 0:
			frappe.throw(_("The rate cannot be negative."))
		duplicate = frappe.db.exists(
			"OneChat Message Rate",
			{"country": self.country, "category": self.category, "name": ["!=", self.name]},
		)
		if duplicate:
			frappe.throw(_("There is already a {0} rate for {1}.").format(self.category, self.country))
