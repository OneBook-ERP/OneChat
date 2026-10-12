import re

import frappe
from frappe import _
from frappe.model.document import Document


class OneChatQuickReply(Document):
	# begin: auto-generated types

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		attach: DF.Attach | None
		message: DF.SmallText | None
		shortcut: DF.Data
		title: DF.Data
	# end: auto-generated types

	def validate(self):
		self.shortcut = (self.shortcut or "").strip().lstrip("/").strip().lower()
		if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", self.shortcut):
			frappe.throw(_("Shortcut can only contain lowercase letters, digits and dashes."))

		if frappe.db.exists(self.doctype, {"shortcut": self.shortcut, "name": ["!=", self.name]}):
			frappe.throw(_("The shortcut /{0} is already in use.").format(self.shortcut))

		self.title = (self.title or "").strip()
		self.message = (self.message or "").strip()
		if not self.message and not self.attach:
			frappe.throw(_("Write a message or add an attachment."))
