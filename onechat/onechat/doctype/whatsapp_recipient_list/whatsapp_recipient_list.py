import json

import frappe
from frappe import _
from frappe.model.document import Document


class WhatsAppRecipientList(Document):
	def validate(self):
		self.validate_recipients()

	def validate_recipients(self):
		if not self.is_new():
			if not self.recipients:
				frappe.throw(_("At least one recipient is required"))

	def import_list_from_doctype(
		self, doctype, mobile_field, name_field=None, filters=None, limit=None, data_fields=None
	):
		self.doctype_to_import = doctype
		self.mobile_field = mobile_field
		self.filters = filters
		if data_fields:
			self.data_fields = json.dumps(data_fields)

		if limit:
			self.import_limit = limit

		fields = [mobile_field]
		if name_field:
			fields.append(name_field)
		if data_fields:
			meta = frappe.get_meta(doctype)
			for field in meta.fields:
				if field.fieldname not in fields and field.fieldname in data_fields:
					fields.append(field.fieldname)
		records = frappe.get_all(doctype, filters=filters, fields=fields, limit=limit)

		self.recipients = []

		for record in records:
			if not record.get(mobile_field):
				continue

			mobile = record.get(mobile_field)
			mobile = "".join(char for char in mobile if char.isdigit() or char == "+")

			if not mobile:
				continue

			recipient_data = {}
			if data_fields:
				for field in data_fields:
					if record.get(field):
						variable_name = field.lower().replace(" ", "_")
						recipient_data[variable_name] = record.get(field)

			recipient = {"mobile_number": mobile, "recipient_data": json.dumps(recipient_data, default=str)}

			if name_field and record.get(name_field):
				recipient["recipient_name"] = record.get(name_field)

			self.append("recipients", recipient)

		return len(self.recipients)
