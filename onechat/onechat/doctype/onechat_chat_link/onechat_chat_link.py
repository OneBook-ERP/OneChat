import frappe
from frappe import _
from frappe.model.document import Document

from onechat.campaigns.chat_links import (
	CODE,
	build_instagram_url,
	build_url,
	lookup_number,
	new_code,
	short_url,
)


class OneChatChatLink(Document):
	def validate(self):
		self.ref_code = (self.ref_code or "").strip().upper() or new_code()
		if not CODE.match(self.ref_code):
			frappe.throw(_("Ref code must be 4 to 12 letters or digits"))

		account = (
			frappe.db.get_value(
				"OneChat Account", self.whatsapp_account, ["channel", "ig_username"], as_dict=True
			)
			or {}
		)
		if account.get("channel") == "Instagram":
			self.display_number = None
			self.link_url = build_instagram_url(account.ig_username, self.ref_code, self.track)
			if not self.link_url:
				frappe.throw(
					_("Test the Instagram account's connection first, so OneChat knows its username.")
				)
		else:
			if not self.display_number:
				self.display_number = lookup_number(self.whatsapp_account)
			self.link_url = build_url(self.display_number, self.prefilled_message, self.ref_code, self.track)
		self.short_url = short_url(self.ref_code) if self.link_url else None
