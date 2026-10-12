import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class OneChatSettings(Document):
	def validate(self):
		from onechat.workspace.retention import MIN_MEDIA_DAYS, MIN_MESSAGE_DAYS

		if not cint(self.get("retention_enabled")):
			return
		if cint(self.get("message_retention_days")) < MIN_MESSAGE_DAYS:
			frappe.throw(_("Keep messages for at least {0} days.").format(MIN_MESSAGE_DAYS))
		if cint(self.get("media_retention_days")) < MIN_MEDIA_DAYS:
			frappe.throw(_("Keep media files for at least {0} days.").format(MIN_MEDIA_DAYS))
		if cint(self.get("media_retention_days")) > cint(self.get("message_retention_days")):
			frappe.throw(_("Media can't be kept longer than the messages they belong to."))
