import json

import frappe
import magic
from frappe import _, throw
from frappe.desk.form.utils import get_pdf_link
from frappe.integrations.utils import make_post_request, make_request
from frappe.model.document import Document

from onechat.utils import get_whatsapp_account


class WhatsAppTemplates(Document):
	def validate(self):
		from onechat.inbox.accounts import require_whatsapp

		require_whatsapp(self.whatsapp_account)
		self.set_whatsapp_account()
		self.link_flow_buttons()
		if not self.language_code or self.has_value_changed("language"):
			lang_code = frappe.db.get_value("Language", self.language) or "en"
			self.language_code = lang_code.replace("-", "_")

		if self.is_new() and self.template_name and not self.actual_name:
			self.actual_name = self.template_name.lower().replace(" ", "_")

		if self.header_type in ["IMAGE", "DOCUMENT"] and self.sample:
			content = self.sample_content()
			self.flags.media_id = self.get_media_id(self.get_session_id(content), content)

		if not self.is_new():
			self.update_template()

	def link_flow_buttons(self):
		for button in self.buttons:
			if button.button_type == "Flow" and button.flow_id and not button.whatsapp_flow:
				button.whatsapp_flow = frappe.db.get_value("WhatsApp Flow", {"flow_id": button.flow_id})

	def set_whatsapp_account(self):
		if not self.whatsapp_account:
			default_whatsapp_account = get_whatsapp_account()
			if not default_whatsapp_account:
				throw(
					_("Please set a default outgoing WhatsApp Account or Select available WhatsApp Account")
				)
			else:
				self.whatsapp_account = default_whatsapp_account.name

	def sample_content(self):
		name = frappe.db.get_value("File", {"file_url": self.sample}, "name")
		if not name:
			frappe.throw(_("Upload the header sample again."))
		return frappe.get_doc("File", name).get_content()

	def get_session_id(self, content):
		meta = self.get_settings()
		payload = {
			"file_length": len(content),
			"file_type": magic.Magic(mime=True).from_buffer(content),
			"messaging_product": "whatsapp",
		}

		response = make_post_request(
			f"{meta.url}/{meta.version}/{meta.app_id}/uploads",
			headers=meta.headers,
			data=json.loads(json.dumps(payload)),
		)
		return response["id"]

	def get_media_id(self, session_id, content):
		meta = self.get_settings()
		headers = {"authorization": f"OAuth {meta.token}"}
		response = make_post_request(f"{meta.url}/{meta.version}/{session_id}", headers=headers, data=content)
		return response["h"]

	def after_insert(self):
		meta = self.get_settings()
		data = {
			"name": self.actual_name,
			"language": self.language_code,
			"category": self.category,
			"components": [],
		}

		body = {
			"type": "BODY",
			"text": self.template,
		}
		if self.sample_values:
			body.update({"example": {"body_text": [self.sample_values.split(",")]}})

		data["components"].append(body)
		if self.header_type:
			data["components"].append(self.get_header())

		if self.footer:
			data["components"].append({"type": "FOOTER", "text": self.footer})

		if self.buttons:
			button_block = {"type": "BUTTONS", "buttons": []}
			for btn in self.buttons:
				b = {"type": btn.button_type, "text": btn.button_label}

				if btn.button_type == "Visit Website":
					b["type"] = "URL"
					b["url"] = btn.website_url
					if btn.url_type == "Dynamic" and btn.example_url:
						b["example"] = btn.example_url.split(",")
				elif btn.button_type == "Call Phone":
					b["type"] = "PHONE_NUMBER"
					b["phone_number"] = btn.phone_number
				elif btn.button_type == "Quick Reply":
					b["type"] = "QUICK_REPLY"

				elif btn.button_type == "Flow":
					b["type"] = "FLOW"
					b["text"] = btn.button_label
					b["flow_id"] = btn.flow_id

				button_block["buttons"].append(b)

			data["components"].append(button_block)

		try:
			response = make_post_request(
				f"{meta.url}/{meta.version}/{meta.business_id}/message_templates",
				headers=meta.headers,
				data=json.dumps(data),
			)
			self.db_set({"id": response["id"], "status": response["status"]})
		except Exception:
			res = frappe.flags.integration_request.json().get("error", {})
			error_message = res.get("error_user_msg", res.get("message"))
			frappe.throw(
				msg=error_message,
				title=res.get("error_user_title", "Error"),
			)

	def update_template(self):
		meta = self.get_settings()
		data = {"components": []}

		body = {
			"type": "BODY",
			"text": self.template,
		}
		if self.sample_values:
			body.update({"example": {"body_text": [self.sample_values.split(",")]}})
		data["components"].append(body)
		if self.header_type:
			data["components"].append(self.get_header())
		if self.footer:
			data["components"].append({"type": "FOOTER", "text": self.footer})
		if self.buttons:
			button_block = {"type": "BUTTONS", "buttons": []}
			for btn in self.buttons:
				b = {"type": btn.button_type, "text": btn.button_label}

				if btn.button_type == "Visit Website":
					b["type"] = "URL"
					b["url"] = btn.website_url
					if btn.url_type == "Dynamic" and btn.example_url:
						b["example"] = btn.example_url.split(",")
				elif btn.button_type == "Call Phone":
					b["type"] = "PHONE_NUMBER"
					b["phone_number"] = btn.phone_number
				elif btn.button_type == "Quick Reply":
					b["type"] = "QUICK_REPLY"
				elif btn.button_type == "Flow":
					b["type"] = "FLOW"
					b["text"] = btn.button_label
					b["flow_id"] = btn.flow_id

				button_block["buttons"].append(b)

			data["components"].append(button_block)

		try:
			res = make_post_request(
				f"{meta.url}/{meta.version}/{self.id}",
				headers=meta.headers,
				data=json.dumps(data),
			)
			frappe.log_error(title="WhatsApp Template Updated", message=res)
		except Exception as e:
			raise e
			res = frappe.flags.integration_request.json()["error"]
			frappe.throw(
				msg=res.get("error_user_msg", res.get("message")),
				title=res.get("error_user_title", "Error"),
			)

	def get_settings(self):
		settings = frappe.get_doc("OneChat Account", self.whatsapp_account)
		token = settings.get_password("token")
		return frappe._dict(
			token=token,
			url=settings.url,
			version=settings.version,
			business_id=settings.business_id,
			app_id=settings.app_id,
			headers={"authorization": f"Bearer {token}", "content-type": "application/json"},
		)

	def on_trash(self):
		meta = self.get_settings()
		url = f"{meta.url}/{meta.version}/{meta.business_id}/message_templates?name={self.actual_name}"
		try:
			make_request("DELETE", url, headers=meta.headers)
		except Exception:
			res = frappe.flags.integration_request.json().get("error", {})
			if res.get("error_user_title") == "Message Template Not Found":
				frappe.msgprint(_("Deleted locally"), res.get("error_user_title", _("Error")), alert=True)
			else:
				frappe.throw(
					msg=res.get("error_user_msg"),
					title=res.get("error_user_title", "Error"),
				)

	def get_header(self):
		header = {"type": "header", "format": self.header_type}
		if self.header_type == "TEXT":
			header["text"] = self.header
			if self.sample:
				samples = self.sample.split(", ")
				header.update({"example": {"header_text": samples}})
		else:
			header.update({"example": {"header_handle": [self.flags.media_id]}})

		return header


def resolve_flow(flow_id, whatsapp_account):
	if not flow_id:
		return None

	name = frappe.db.get_value("WhatsApp Flow", {"flow_id": flow_id})
	if name or not whatsapp_account:
		return name

	try:
		from onechat.onechat.doctype.whatsapp_flow.whatsapp_flow import import_flow

		return import_flow(whatsapp_account, flow_id)
	except Exception:
		frappe.log_error(title=f"OneChat: could not import WhatsApp flow {flow_id}")
		return None


@frappe.whitelist(methods=["POST"])
def fetch():
	from onechat.workspace.session import require, require_admin

	require_admin()
	require("WhatsApp Templates", "create")
	whatsapp_accounts = frappe.get_all(
		"OneChat Account",
		filters={"status": "Active"},
		fields=["name", "account_name", "token", "url", "version", "business_id"],
	)
	fetched, problems = [], []

	for account in whatsapp_accounts:
		if not account.business_id:
			problems.append(
				_("{0}: add the WhatsApp Business Account ID first.").format(
					account.account_name or account.name
				)
			)
			continue
		token = frappe.get_doc("OneChat Account", account.name).get_password("token")
		url = account.url
		version = account.version
		business_id = account.business_id

		headers = {"authorization": f"Bearer {token}", "content-type": "application/json"}

		try:
			response = make_request(
				"GET",
				f"{url}/{version}/{business_id}/message_templates",
				headers=headers,
			)

			for template in response["data"]:
				if frappe.db.exists("WhatsApp Templates", {"actual_name": template["name"]}):
					doc = frappe.get_doc("WhatsApp Templates", {"actual_name": template["name"]})
				else:
					doc = frappe.new_doc("WhatsApp Templates")
					doc.template_name = template["name"]
					doc.actual_name = template["name"]

				doc.status = template["status"]
				doc.language_code = template["language"]
				doc.category = template["category"]
				doc.id = template["id"]
				doc.whatsapp_account = account.name
				score = (template.get("quality_score") or {}).get("score")
				if score:
					doc.quality_score = score
				if "rejected_reason" in template:
					reason = template["rejected_reason"]
					doc.rejected_reason = reason if reason and reason != "NONE" else None

				for component in template["components"]:
					if component["type"] == "HEADER":
						doc.header_type = component["format"]

						if component["format"] == "TEXT":
							doc.header = component["text"]
					elif component["type"] == "FOOTER":
						doc.footer = component["text"]

					elif component["type"] == "BODY":
						doc.template = component["text"]
						if component.get("example"):
							if component["example"].get("body_text"):
								doc.sample_values = ",".join(component["example"]["body_text"][0])

					elif component["type"] == "BUTTONS":
						doc.set("buttons", [])
						frappe.db.delete(
							"WhatsApp Button", {"parent": doc.name, "parenttype": "WhatsApp Templates"}
						)
						typeMap = {
							"URL": "Visit Website",
							"PHONE_NUMBER": "Call Phone",
							"QUICK_REPLY": "Quick Reply",
							"FLOW": "Flow",
						}

						for i, button in enumerate(component.get("buttons", []), start=1):
							btn = {}
							btn["button_type"] = typeMap[button["type"]]
							btn["button_label"] = button.get("text")
							btn["sequence"] = i

							if button["type"] == "URL":
								btn["website_url"] = button.get("url")
								if "{{" in btn["website_url"]:
									btn["url_type"] = "Dynamic"
								else:
									btn["url_type"] = "Static"

								if button.get("example"):
									btn["example_url"] = ",".join(button["example"])
							elif button["type"] == "PHONE_NUMBER":
								btn["phone_number"] = button.get("phone_number")
							elif button["type"] == "FLOW":
								btn["flow_id"] = button.get("flow_id")
								btn["whatsapp_flow"] = resolve_flow(btn["flow_id"], account.name)

							doc.append("buttons", btn)

				upsert_doc_without_hooks(doc, "WhatsApp Button", "buttons")

			fetched.append(account.account_name or account.name)

		except Exception as e:
			problems.append(f"{account.account_name or account.name}: {fetch_error(account, e)}")

	if problems and not fetched:
		frappe.throw("<br>".join(problems), title=_("Could not fetch templates"))
	if problems:
		return _("Fetched templates for {0}. Skipped: {1}").format(", ".join(fetched), " ".join(problems))
	return (
		_("Fetched templates for {0}").format(", ".join(fetched))
		if fetched
		else _("No active WhatsApp accounts to fetch from")
	)


def fetch_error(account, error):
	from onechat.whatsapp.accounts import is_wrong_node, wrong_business_id

	message = ""
	request = getattr(frappe.flags, "integration_request", None)
	if request is not None and hasattr(request, "json"):
		try:
			detail = request.json().get("error", {}) or {}
			message = detail.get("error_user_msg") or detail.get("message") or ""
		except ValueError:
			message = ""
	message = message or str(error)
	return wrong_business_id(account) if is_wrong_node(message) else message


def upsert_doc_without_hooks(doc, child_dt, child_field):
	if frappe.db.exists(doc.doctype, doc.name):
		doc.db_update()
		frappe.db.delete(child_dt, {"parent": doc.name, "parenttype": doc.doctype})
	else:
		doc.db_insert()
	for d in doc.get(child_field):
		d.parent = doc.name
		d.parenttype = doc.doctype
		d.parentfield = child_field
		d.db_insert()
	frappe.db.commit()
