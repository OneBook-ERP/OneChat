import json

import frappe
from frappe import _, throw
from frappe.integrations.utils import make_post_request
from frappe.model.document import Document

from onechat.utils import format_number, get_whatsapp_account
from onechat.workspace.session import require_app_user


class OneChatMessage(Document):
	def validate(self):
		self.set_whatsapp_account()
		if (
			not self.get("whatsapp_contact")
			and self.reference_doctype == "OneChat Contact"
			and self.reference_name
		):
			self.whatsapp_contact = self.reference_name

	def set_whatsapp_account(self):
		if not self.whatsapp_account and self.type == "Outgoing":
			contact = self.get("whatsapp_contact") or (
				self.reference_name if self.reference_doctype == "OneChat Contact" else None
			)
			if contact:
				self.whatsapp_account = frappe.db.get_value("OneChat Contact", contact, "whatsapp_account")
		if not self.whatsapp_account:
			account_type = "outgoing" if self.type == "Outgoing" else "incoming"
			default_whatsapp_account = get_whatsapp_account(account_type=account_type)
			if not default_whatsapp_account:
				throw(_("Set a default outgoing account, or pick the account to send from."))
			else:
				self.whatsapp_account = default_whatsapp_account.name
		elif (
			self.type == "Outgoing"
			and frappe.db.get_value("OneChat Account", self.whatsapp_account, "status") == "Inactive"
		):
			throw(
				_("Account {0} is inactive. Activate it in Settings to send messages.").format(
					self.whatsapp_account
				)
			)

	def before_insert(self):
		from onechat.inbox.consent import check_outgoing

		if self.flags.skip_send:
			self.set_whatsapp_account()
			return
		check_outgoing(self)
		self.set_whatsapp_account()
		if (
			self.type == "Outgoing"
			and frappe.db.get_value("OneChat Account", self.whatsapp_account, "channel") == "Instagram"
		):
			from onechat.instagram.send import deliver

			deliver(self)
			return
		if self.type == "Outgoing" and self.message_type != "Template":
			from onechat.whatsapp.media import reference

			media = reference(self.whatsapp_account, self.attach) if self.attach else {}

			data = {
				"messaging_product": "whatsapp",
				"to": format_number(self.to),
				"type": self.content_type,
			}
			if self.is_reply and self.reply_to_message_id:
				data["context"] = {"message_id": self.reply_to_message_id}
			if self.content_type in ["document", "image", "video"]:
				data[self.content_type.lower()] = {**media, "caption": self.message}
			elif self.content_type == "reaction":
				data["reaction"] = {
					"message_id": self.reply_to_message_id,
					"emoji": self.message,
				}
			elif self.content_type == "text":
				data["text"] = {"preview_url": True, "body": self.message}

			elif self.content_type == "audio":
				data["audio"] = media

			elif self.content_type == "interactive":
				data["type"] = "interactive"
				buttons_data = json.loads(self.buttons) if isinstance(self.buttons, str) else self.buttons

				if isinstance(buttons_data, dict):
					data["interactive"] = self.interactive_payload(buttons_data)
				elif isinstance(buttons_data, list) and len(buttons_data) > 3:
					data["interactive"] = {
						"type": "list",
						"body": {"text": self.message},
						"action": {
							"button": "Select Option",
							"sections": [
								{
									"title": "Options",
									"rows": [
										{
											"id": btn["id"],
											"title": btn["title"],
											"description": btn.get("description", ""),
										}
										for btn in buttons_data[:10]
									],
								}
							],
						},
					}
				else:
					data["interactive"] = {
						"type": "button",
						"body": {"text": self.message},
						"action": {
							"buttons": [
								{"type": "reply", "reply": {"id": btn["id"], "title": btn["title"]}}
								for btn in buttons_data[:3]
							]
						},
					}

			elif self.content_type in ("order_details", "order_status"):
				data["type"] = "interactive"
				data["interactive"] = (
					json.loads(self.products) if isinstance(self.products, str) else self.products
				)

			elif self.content_type in ("product", "product_list"):
				data["type"] = "interactive"
				data["interactive"] = self.product_payload()

			elif self.content_type == "flow":
				if not self.flow:
					frappe.throw(_("WhatsApp Flow is required for flow content type"))

				flow_doc = frappe.get_doc("WhatsApp Flow", self.flow)

				if not flow_doc.flow_id:
					frappe.throw(_("Flow must be created on WhatsApp before sending"))

				flow_mode = None
				if flow_doc.status != "Published":
					flow_mode = "draft"
					frappe.msgprint(_("Sending flow in draft mode (for testing only)"), indicator="orange")

				flow_screen = self.flow_screen
				if not flow_screen and flow_doc.screens:
					flow_screen = flow_doc.screens[0].screen_id

				data["type"] = "interactive"
				data["interactive"] = {
					"type": "flow",
					"body": {"text": self.message or "Please fill out the form"},
					"action": {
						"name": "flow",
						"parameters": {
							"flow_message_version": "3",
							"flow_id": flow_doc.flow_id,
							"flow_cta": self.flow_cta or flow_doc.flow_cta or "Open",
							"flow_action": "navigate",
							"flow_action_payload": {"screen": flow_screen},
						},
					},
				}

				if flow_mode:
					data["interactive"]["action"]["parameters"]["mode"] = flow_mode

				flow_token = self.flow_token or frappe.generate_hash(length=16)
				self.flow_token = flow_token
				data["interactive"]["action"]["parameters"]["flow_token"] = flow_token

			try:
				self.notify(data)
				self.status = "Success"
			except Exception as e:
				self.status = "Failed"
				frappe.throw(f"Failed to send message {e!s}")
		elif self.type == "Outgoing" and self.message_type == "Template" and not self.message_id:
			self.send_template()

	def interactive_payload(self, spec):
		options = spec.get("options") or []
		if spec.get("type") == "cta_url":
			payload = {
				"type": "cta_url",
				"body": {"text": (self.message or "")[:1024]},
				"action": {
					"name": "cta_url",
					"parameters": {
						"display_text": (spec.get("button") or "Open")[:20],
						"url": spec.get("url"),
					},
				},
			}
		elif spec.get("type") == "list":
			payload = {
				"type": "list",
				"body": {"text": (self.message or "")[:1024]},
				"action": {
					"button": (spec.get("button") or "Choose")[:20],
					"sections": [
						{
							"title": (spec.get("section") or spec.get("button") or "Options")[:24],
							"rows": [
								{
									k: v
									for k, v in {
										"id": row["id"],
										"title": row["title"][:24],
										"description": (row.get("description") or "")[:72],
									}.items()
									if v
								}
								for row in options[:10]
							],
						}
					],
				},
			}
		else:
			payload = {
				"type": "button",
				"body": {"text": (self.message or "")[:1024]},
				"action": {
					"buttons": [
						{"type": "reply", "reply": {"id": row["id"], "title": row["title"][:20]}}
						for row in options[:3]
					]
				},
			}

		if spec.get("header"):
			payload["header"] = {"type": "text", "text": spec["header"][:60]}
		if spec.get("footer"):
			payload["footer"] = {"text": spec["footer"][:60]}
		return payload

	def product_payload(self):
		products = json.loads(self.products) if isinstance(self.products, str) else (self.products or {})
		items = [code for code in products.get("items") or [] if code][:30]
		catalog_id = frappe.db.get_value("OneChat Account", self.whatsapp_account, "catalog_id")
		if not catalog_id:
			frappe.throw(_("Set a catalog ID on WhatsApp account {0} first.").format(self.whatsapp_account))
		if not items:
			frappe.throw(_("Pick at least one product to send."))

		body = (products.get("body") or "").strip()
		if self.content_type == "product":
			payload = {
				"type": "product",
				"action": {"catalog_id": catalog_id, "product_retailer_id": items[0]},
			}
			if body:
				payload["body"] = {"text": body[:1024]}
			return payload

		header = (products.get("header") or _("Our products")).strip()
		return {
			"type": "product_list",
			"header": {"type": "text", "text": header[:60]},
			"body": {"text": (body or _("Take a look at these products"))[:1024]},
			"action": {
				"catalog_id": catalog_id,
				"sections": [
					{
						"title": header[:24],
						"product_items": [{"product_retailer_id": code} for code in items],
					}
				],
			},
		}

	def send_template(self):
		template = frappe.get_doc("WhatsApp Templates", self.template)
		frappe.log_error(title="WhatsApp template", message=template)
		data = {
			"messaging_product": "whatsapp",
			"to": format_number(self.to),
			"type": "template",
			"template": {
				"name": template.actual_name or template.template_name,
				"language": {"code": template.language_code},
				"components": [],
			},
		}

		if template.sample_values or self.body_param:
			field_names = (template.field_names or template.sample_values or "").split(",")
			parameters = []
			template_parameters = []

			if self.body_param is not None:
				params = list(json.loads(self.body_param).values())
				for param in params:
					parameters.append({"type": "text", "text": param})
					template_parameters.append(param)
			elif self.flags.custom_ref_doc:
				custom_values = self.flags.custom_ref_doc
				for field_name in field_names:
					value = custom_values.get(field_name.strip())
					parameters.append({"type": "text", "text": value})
					template_parameters.append(value)

			else:
				ref_doc = frappe.get_doc(self.reference_doctype, self.reference_name)
				for field_name in field_names:
					value = ref_doc.get_formatted(field_name.strip())
					parameters.append({"type": "text", "text": value})
					template_parameters.append(value)

			self.template_parameters = json.dumps(template_parameters)
			data["template"]["components"].append(
				{
					"type": "body",
					"parameters": parameters,
				}
			)

		file_url = self.attach or template.sample
		if template.header_type in ("IMAGE", "DOCUMENT", "VIDEO") and file_url:
			from onechat.whatsapp.media import reference

			self.attach = file_url

			kind = template.header_type.lower()
			media = reference(self.whatsapp_account, file_url)
			if kind == "document":
				media["filename"] = file_url.rsplit("/", 1)[-1]
			data["template"]["components"].append(
				{
					"type": "header",
					"parameters": [{"type": kind, kind: media}],
				}
			)

		if template.buttons:
			button_parameters = []
			for idx, btn in enumerate(template.buttons):
				if btn.button_type == "Quick Reply":
					button_parameters.append(
						{
							"type": "button",
							"sub_type": "quick_reply",
							"index": str(idx),
							"parameters": [{"type": "payload", "payload": btn.button_label}],
						}
					)
				elif btn.button_type == "Call Phone":
					button_parameters.append(
						{
							"type": "button",
							"sub_type": "phone_number",
							"index": str(idx),
							"parameters": [{"type": "text", "text": btn.phone_number}],
						}
					)
				elif btn.button_type == "Visit Website":
					url = btn.website_url
					if btn.url_type == "Dynamic":
						ref_doc = frappe.get_doc(self.reference_doctype, self.reference_name)
						url = ref_doc.get_formatted(btn.website_url)
					button_parameters.append(
						{
							"type": "button",
							"sub_type": "url",
							"index": str(idx),
							"parameters": [{"type": "text", "text": url}],
						}
					)

				elif btn.button_type == "Flow":
					self.flow_token = self.flow_token or frappe.generate_hash(length=16)
					if btn.whatsapp_flow and not self.flow:
						self.flow = btn.whatsapp_flow
					button_parameters.append(
						{
							"type": "button",
							"sub_type": "flow",
							"index": str(idx),
							"parameters": [{"type": "action", "action": {"flow_token": self.flow_token}}],
						}
					)
			if button_parameters:
				data["template"]["components"].extend(button_parameters)

		self.notify(data)

	def notify(self, data):
		frappe.log_error(title="WhatsApp data", message=data)
		whatsapp_account = frappe.get_doc(
			"OneChat Account",
			self.whatsapp_account,
		)
		token = whatsapp_account.get_password("token")

		headers = {
			"authorization": f"Bearer {token}",
			"content-type": "application/json",
		}
		try:
			response = make_post_request(
				f"{whatsapp_account.url}/{whatsapp_account.version}/{whatsapp_account.phone_id}/messages",
				headers=headers,
				data=json.dumps(data),
			)
			self.message_id = response["messages"][0]["id"]

		except Exception:
			res = frappe.flags.integration_request.json().get("error", {})
			error_message = res.get("Error", res.get("message"))
			frappe.get_doc(
				{
					"doctype": "WhatsApp Notification Log",
					"template": "Text Message",
					"meta_data": frappe.flags.integration_request.json(),
				}
			).insert(ignore_permissions=True)

			frappe.throw(msg=error_message, title=res.get("error_user_title", "Error"))

	def format_number(self, number):
		if number.startswith("+"):
			number = number[1 : len(number)]

		return number

	@frappe.whitelist()
	def send_read_receipt(self):
		data = {"messaging_product": "whatsapp", "status": "read", "message_id": self.message_id}

		settings = frappe.get_doc(
			"OneChat Account",
			self.whatsapp_account,
		)

		token = settings.get_password("token")

		headers = {
			"authorization": f"Bearer {token}",
			"content-type": "application/json",
		}
		try:
			response = make_post_request(
				f"{settings.url}/{settings.version}/{settings.phone_id}/messages",
				headers=headers,
				data=json.dumps(data),
			)

			if response.get("success"):
				self.status = "marked as read"
				self.save()
				return response.get("success")

		except Exception:
			res = frappe.flags.integration_request.json().get("error", {})
			error_message = res.get("Error", res.get("message"))
			frappe.log_error("WhatsApp API Error", f"{error_message}\n{res}")


def on_doctype_update():
	frappe.db.add_index("OneChat Message", ["reference_doctype", "reference_name"])


@frappe.whitelist()
def send_template(to: str | int, reference_doctype: str, reference_name: str, template: str):
	require_app_user()
	try:
		doc = frappe.get_doc(
			{
				"doctype": "OneChat Message",
				"to": to,
				"type": "Outgoing",
				"message_type": "Template",
				"reference_doctype": reference_doctype,
				"reference_name": reference_name,
				"content_type": "text",
				"template": template,
			}
		)

		doc.save()
	except Exception as e:
		raise e
