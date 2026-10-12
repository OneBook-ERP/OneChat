import frappe
from frappe.model.document import Document


class OneChatContact(Document):
	# begin: auto-generated types

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		contact_name: DF.Data | None
		disable: DF.Check
		email: DF.Data | None
		mobile_no: DF.Data | None
		profile_image: DF.AttachImage | None
		reference_docname: DF.Data | None
		reference_doctype: DF.Data | None
		wa_number: DF.Data | None
		assigned_to: DF.Link | None
		conversation_status: DF.Literal["Open", "Pending", "Resolved"]
		resolved_by: DF.Link | None
		resolved_at: DF.Datetime | None
		unread_count: DF.Int
		last_message_at: DF.Datetime | None
		last_message_type: DF.Data | None
		last_message: DF.SmallText | None
		labels: DF.TableMultiSelect
		links: DF.Table
		opted_out: DF.Check
		opted_out_at: DF.Datetime | None
		team: DF.Link | None
		sla_due_at: DF.Datetime | None
		first_response_at: DF.Datetime | None
	# end: auto-generated types

	def validate(self):
		from onechat.inbox.conversations import digits

		self.wa_number = digits(self.mobile_no)
		from onechat.integrations import auto_link, links

		if self.is_new():
			if self.reference_doctype and self.reference_docname:
				links.attach(self, self.reference_doctype, self.reference_docname)
			for doctype, name in auto_link(self):
				links.attach(self, doctype, name)
		elif self.wa_number and not (self.get_doc_before_save() or {}).get("wa_number"):
			for doctype, name in auto_link(self):
				links.attach(self, doctype, name)

	def after_insert(self):
		if self.email:
			frappe.publish_realtime(
				"new_room_creation", {"user": self.email, "room_name": self.contact_name}, user=self.email
			)

	def before_insert(self):
		self.validate_mobile_no()

	def validate_mobile_no(self):
		if self.mobile_no and len(self.mobile_no) <= 10:
			from onechat.integrations import setting

			extension = setting("default_country_code")
			if extension:
				self.mobile_no = f"{extension}{self.mobile_no}"
