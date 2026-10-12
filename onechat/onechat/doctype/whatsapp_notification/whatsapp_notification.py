import json

import frappe
from frappe import _, _dict
from frappe.desk.form.utils import get_pdf_link
from frappe.integrations.utils import make_post_request
from frappe.model.document import Document
from frappe.utils import add_to_date, datetime, nowdate
from frappe.utils.safe_exec import get_safe_globals

from onechat.inbox.consent import is_opted_out
from onechat.utils import get_whatsapp_account
from onechat.workspace.session import require_admin


class WhatsAppNotification(Document):
	def validate(self):
		if self.send_plain_message:
			if not self.mobile_numbers and not self.field_name:
				frappe.throw(
					_("Please enter at least one Mobile Number or Field Name for plain message sending.")
				)
			if not self.message_body:
				frappe.throw(_("Please enter the Message Body for plain message sending."))
			return

		if self.notification_type == "DocType Event":
			if not self.field_name and not self.mobile_numbers:
				frappe.throw(
					_("Please enter at least one Field Name or Mobile Number for template notification.")
				)
			if self.field_name:
				fields = frappe.get_doc("DocType", self.reference_doctype).fields
				fields += frappe.get_all(
					"Custom Field", filters={"dt": self.reference_doctype}, fields=["fieldname"]
				)
				if not any(field.fieldname == self.field_name for field in fields):
					frappe.throw(_("Field name {0} does not exists").format(self.field_name))

		if self.custom_attachment:
			if not self.attach and not self.attach_from_field:
				frappe.throw(
					_("Either {0} a file or add a {1} to send attachemt").format(
						frappe.bold(_("Attach")),
						frappe.bold(_("Attach from field")),
					)
				)

		if self.set_property_after_alert:
			meta = frappe.get_meta(self.reference_doctype)
			if not meta.get_field(self.set_property_after_alert):
				frappe.throw(
					_("Field {0} not found on DocType {1}").format(
						self.set_property_after_alert,
						self.reference_doctype,
					)
				)

	def send_scheduled_message(self) -> dict:
		if self.send_plain_message:
			self.send_plain_message_to_numbers()
			return

		if self.condition and not frappe.safe_eval(self.condition, get_safe_globals(), dict(doc=self)):
			return

		template = frappe.db.get_value("WhatsApp Templates", self.template, fieldname="*")

		if template and template.language_code:
			if self.get("_contact_list"):
				self.send_simple_template(template)
			elif self.get("_data_list"):
				for data in self._data_list:
					doc = frappe.get_doc(self.reference_doctype, data.get("name"))

					self.send_template_message(doc, data.get("phone_no"), template, True)
			elif self.mobile_numbers:
				self.send_simple_template(template)

	def send_simple_template(self, template, contact_list=None):
		contacts = contact_list or self.get("_contact_list") or []
		if not contacts and self.mobile_numbers:
			contacts = [n.strip() for n in self.mobile_numbers.split(",") if n.strip()]

		for contact in contacts:
			data = {
				"messaging_product": "whatsapp",
				"to": self.format_number(contact),
				"type": "template",
				"template": {
					"name": template.actual_name,
					"language": {"code": template.language_code},
					"components": [],
				},
			}
			self.content_type = template.get("header_type", "text").lower()
			self.notify(data, template_account=template.get("whatsapp_account"))

	def send_template_message(
		self, doc: Document, phone_no=None, default_template=None, ignore_condition=False
	):
		if self.disabled:
			return

		if self.send_plain_message:
			self.send_plain_message_to_numbers(doc)
			return

		doc_data = doc.as_dict()
		if self.condition and not ignore_condition:
			if not frappe.safe_eval(self.condition, get_safe_globals(), dict(doc=doc_data)):
				return

		template = default_template or frappe.get_doc("WhatsApp Templates", self.template)

		if template:
			recipients = []
			if phone_no:
				recipients.append(phone_no)
			else:
				if self.field_name and doc_data.get(self.field_name):
					recipients.append(doc_data.get(self.field_name))
				if self.mobile_numbers:
					numbers = [n.strip() for n in self.mobile_numbers.split(",") if n.strip()]
					recipients.extend(numbers)

			recipients = list(dict.fromkeys(recipients))

			components = []
			if self.fields:
				parameters = []
				for field in self.fields:
					if isinstance(doc, Document):
						value = doc.get_formatted(field.field_name)
					else:
						value = doc_data[field.field_name]
						if isinstance(doc_data[field.field_name], datetime.date | datetime.datetime):
							value = str(doc_data[field.field_name])

					parameters.append({"type": "text", "text": value})

				components.append({"type": "body", "parameters": parameters})

			from onechat.whatsapp.media import reference

			account_name = template.get("whatsapp_account") or (
				get_whatsapp_account(account_type="outgoing") or frappe._dict()
			).get("name")
			media = None
			if self.attach_document_print:
				key = doc.get_document_share_key()
				frappe.db.commit()
				print_format = "Standard"
				doctype = frappe.get_doc("DocType", doc_data["doctype"])
				if doctype.custom:
					if doctype.default_print_format:
						print_format = doctype.default_print_format
				else:
					default_print_format = frappe.db.get_value(
						"Property Setter",
						filters={"doc_type": doc_data["doctype"], "property": "default_print_format"},
						fieldname="value",
					)
					print_format = default_print_format if default_print_format else print_format
				link = get_pdf_link(doc_data["doctype"], doc_data["name"], print_format=print_format)

				filename = f"{doc_data['name']}.pdf"
				media = {"link": f"{frappe.utils.get_url()}{link}&key={key}"}
				self.header_file = media["link"]

			elif self.custom_attachment:
				file_url = doc_data.get(self.attach_from_field) if self.attach_from_field else self.attach
				if not file_url:
					frappe.throw(_("There is no file to attach for {0}.").format(doc_data.get("name")))
				filename = self.file_name or file_url.rsplit("/", 1)[-1]
				media = reference(account_name, file_url)
				self.header_file = file_url

			elif template.header_type in ("DOCUMENT", "IMAGE"):
				if not template.sample:
					frappe.throw(
						_(
							"Template {0} has no header file. Upload one on the template, or pick Document print or Custom file on this notification."
						).format(template.name)
					)
				filename = self.file_name or template.sample.rsplit("/", 1)[-1]
				media = reference(account_name, template.sample)
				self.header_file = template.sample

			if media and template.header_type == "DOCUMENT":
				components.append(
					{
						"type": "header",
						"parameters": [{"type": "document", "document": {**media, "filename": filename}}],
					}
				)
			elif media and template.header_type == "IMAGE":
				components.append(
					{
						"type": "header",
						"parameters": [{"type": "image", "image": media}],
					}
				)
			self.content_type = template.header_type.lower()

			if template.buttons:
				button_fields = self.button_fields.split(",") if self.button_fields else []
				for idx, btn in enumerate(template.buttons):
					if btn.button_type == "Visit Website" and btn.url_type == "Dynamic":
						if button_fields:
							components.append(
								{
									"type": "button",
									"sub_type": "url",
									"index": str(idx),
									"parameters": [{"type": "text", "text": doc.get(button_fields.pop(0))}],
								}
							)

					elif btn.button_type == "Flow":
						components.append(
							{
								"type": "button",
								"sub_type": "Flow",
								"index": str(idx),
							}
						)

			marketing = template.category == "MARKETING"
			for phone_number in recipients:
				if marketing and is_opted_out(number=phone_number):
					continue

				data = {
					"messaging_product": "whatsapp",
					"to": self.format_number(phone_number),
					"type": "template",
					"template": {
						"name": template.actual_name,
						"language": {"code": template.language_code},
						"components": components,
					},
				}
				self.notify(data, doc_data, template_account=template.whatsapp_account)

	def notify(self, data, doc_data=None, template_account=None):
		if template_account:
			whatsapp_account = frappe.get_doc("OneChat Account", template_account)
		else:
			whatsapp_account = get_whatsapp_account(account_type="outgoing")

		if not whatsapp_account:
			frappe.throw(_("Please set a default outgoing WhatsApp Account"))

		token = whatsapp_account.get_password("token")

		headers = {"authorization": f"Bearer {token}", "content-type": "application/json"}
		try:
			success = False
			response = make_post_request(
				f"{whatsapp_account.url}/{whatsapp_account.version}/{whatsapp_account.phone_id}/messages",
				headers=headers,
				data=json.dumps(data),
			)

			if not self.get("content_type"):
				self.content_type = "text"

			parameters = None
			body = next((part for part in data["template"]["components"] if part.get("type") == "body"), None)
			if body:
				parameters = frappe.json.dumps(
					[param.get("text") for param in body.get("parameters") or []], default=str
				)

			new_doc = {
				"doctype": "OneChat Message",
				"type": "Outgoing",
				"source": "Notification",
				"message": str(data["template"]),
				"to": data["to"],
				"message_type": "Template",
				"message_id": response["messages"][0]["id"],
				"content_type": self.content_type,
				"use_template": 1,
				"template": self.template,
				"template_parameters": parameters,
				"whatsapp_account": whatsapp_account.name,
				"attach": self.get("header_file"),
			}

			if doc_data:
				new_doc.update(
					{
						"reference_doctype": doc_data.doctype,
						"reference_name": doc_data.name,
					}
				)

			message = frappe.get_doc(new_doc)
			message.flags.consent_checked = True
			message.save(ignore_permissions=True)

			if doc_data and self.set_property_after_alert and self.property_value:
				if doc_data.doctype and doc_data.name:
					fieldname = self.set_property_after_alert
					value = self.property_value
					meta = frappe.get_meta(doc_data.get("doctype"))
					df = meta.get_field(fieldname)
					if df:
						if df.fieldtype in frappe.model.numeric_fieldtypes:
							value = frappe.utils.cint(value)

						frappe.db.set_value(doc_data.get("doctype"), doc_data.get("name"), fieldname, value)

			frappe.msgprint(_("WhatsApp Message Triggered"), indicator="green", alert=True)
			success = True

		except Exception as e:
			error_message = str(e)
			if frappe.flags.integration_request:
				response = frappe.flags.integration_request.json().get("error", {})
				if response:
					error_message = response.get("Error", response.get("message"))

			frappe.msgprint(
				f"Failed to trigger whatsapp message: {error_message}", indicator="red", alert=True
			)
		finally:
			if not success:
				meta = {"error": error_message}
			else:
				meta = frappe.flags.integration_request.json()
			frappe.get_doc(
				{"doctype": "WhatsApp Notification Log", "template": self.template, "meta_data": meta}
			).insert(ignore_permissions=True)

	def on_trash(self):
		frappe.cache().delete_value("whatsapp_notification_map")

	def send_plain_message_to_numbers(self, doc=None):
		recipients = []
		if doc and self.field_name:
			doc_data = doc.as_dict() if isinstance(doc, Document) else doc
			fn_val = doc_data.get(self.field_name)
			if fn_val:
				recipients.append(str(fn_val))

		if self.mobile_numbers:
			numbers = [n.strip() for n in self.mobile_numbers.split(",") if n.strip()]
			recipients.extend(numbers)

		recipients = list(dict.fromkeys(recipients))

		if not recipients or not self.message_body:
			return

		body = self.message_body
		if self.fields and doc:
			doc_data = doc.as_dict() if isinstance(doc, Document) else doc
			for idx, field in enumerate(self.fields, start=1):
				try:
					if isinstance(doc, Document):
						value = doc.get_formatted(field.field_name)
					else:
						value = doc_data.get(field.field_name, "")
						if isinstance(value, datetime.date | datetime.datetime):
							value = str(value)
				except Exception:
					value = ""
				body = body.replace("{{" + str(idx) + "}}", str(value) if value is not None else "")

		for number in recipients:
			self.notify_text(number, body)

	def notify_text(self, phone_no, body):
		if self.disabled:
			return

		whatsapp_account = get_whatsapp_account(account_type="outgoing")
		if not whatsapp_account:
			frappe.throw(_("Please set a default outgoing WhatsApp Account"))

		token = whatsapp_account.get_password("token")
		headers = {"authorization": f"Bearer {token}", "content-type": "application/json"}

		formatted_number = self.format_number(phone_no)
		data = {
			"messaging_product": "whatsapp",
			"to": formatted_number,
			"type": "text",
			"text": {"body": body},
		}

		success = False
		error_message = ""
		try:
			response = make_post_request(
				f"{whatsapp_account.url}/{whatsapp_account.version}/{whatsapp_account.phone_id}/messages",
				headers=headers,
				data=json.dumps(data),
			)

			frappe.get_doc(
				{
					"doctype": "OneChat Message",
					"type": "Outgoing",
					"source": "Notification",
					"message": body,
					"to": formatted_number,
					"message_type": "Manual",
					"message_id": response["messages"][0]["id"],
					"content_type": "text",
					"use_template": 0,
					"whatsapp_account": whatsapp_account.name,
				}
			).save(ignore_permissions=True)

			frappe.msgprint(_("WhatsApp Message Triggered"), indicator="green", alert=True)
			success = True

		except Exception as e:
			error_message = str(e)
			if frappe.flags.integration_request:
				resp = frappe.flags.integration_request.json().get("error", {})
				if resp:
					error_message = resp.get("Error", resp.get("message", error_message))

			frappe.msgprint(
				f"Failed to send plain WhatsApp message: {error_message}", indicator="red", alert=True
			)
		finally:
			meta = frappe.flags.integration_request.json() if success else {"error": error_message}
			frappe.get_doc(
				{"doctype": "WhatsApp Notification Log", "template": self.name, "meta_data": meta}
			).insert(ignore_permissions=True)

	def format_number(self, number):
		if number.startswith("+"):
			number = number[1 : len(number)]

		return number

	def get_documents_for_today(self):
		diff_days = self.days_in_advance
		if self.doctype_event == "Days After":
			diff_days = -diff_days

		reference_date = add_to_date(nowdate(), days=diff_days)
		reference_date_start = reference_date + " 00:00:00.000000"
		reference_date_end = reference_date + " 23:59:59.000000"

		doc_list = frappe.get_all(
			self.reference_doctype,
			fields="name",
			filters=[
				{self.date_changed: (">=", reference_date_start)},
				{self.date_changed: ("<=", reference_date_end)},
			],
		)

		for d in doc_list:
			doc = frappe.get_doc(self.reference_doctype, d.name)
			self.send_template_message(doc)


@frappe.whitelist()
def call_trigger_notifications():
	require_admin()
	try:
		trigger_notifications()
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Error in call_trigger_notifications")
		raise e


def trigger_notifications(method="daily"):
	if frappe.flags.in_import or frappe.flags.in_patch:
		return

	if method == "daily":
		doc_list = frappe.get_all(
			"WhatsApp Notification",
			filters={"doctype_event": ("in", ("Days Before", "Days After")), "disabled": 0},
		)
		for d in doc_list:
			alert = frappe.get_doc("WhatsApp Notification", d.name)
			alert.get_documents_for_today()
