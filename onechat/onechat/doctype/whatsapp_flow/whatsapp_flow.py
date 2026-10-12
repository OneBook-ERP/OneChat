import json

import frappe
from frappe import _
from frappe.integrations.utils import make_post_request, make_request
from frappe.model.document import Document

from onechat.workspace.session import require, require_admin


class WhatsAppFlow(Document):
	def before_save(self):
		self.flow_json = json.dumps(self.generate_flow_json(), indent=2)

	def validate(self):
		from onechat.inbox.accounts import require_whatsapp

		require_whatsapp(self.whatsapp_account)
		self.validate_screens()

	def validate_screens(self):
		if not self.screens:
			frappe.throw(_("At least one screen is required"))

		screen_ids = []
		terminal_count = 0

		for screen in self.screens:
			if screen.screen_id in screen_ids:
				frappe.throw(_("Duplicate screen ID: {0}").format(screen.screen_id))
			screen_ids.append(screen.screen_id)

			if screen.terminal:
				terminal_count += 1

		if terminal_count == 0:
			frappe.throw(_("At least one screen must be marked as terminal"))

	def generate_flow_json(self):
		flow = {"version": self.data_api_version or "6.0", "screens": []}

		screen_incoming_data = self.build_screen_data_map()

		for screen in self.screens:
			screen_data = self.build_screen(screen, screen_incoming_data.get(screen.screen_id, {}))
			flow["screens"].append(screen_data)

		return flow

	def build_screen_data_map(self):
		screen_data_map = {}
		accumulated_fields = {}

		for screen in self.screens:
			if accumulated_fields:
				screen_data_map[screen.screen_id] = accumulated_fields.copy()

			for field in self.fields:
				if field.screen != screen.screen_id:
					continue
				if not field.enabled:
					continue
				if field.field_type not in [
					"TextHeading",
					"TextSubheading",
					"TextBody",
					"TextCaption",
					"Image",
					"EmbeddedLink",
					"Footer",
				]:
					accumulated_fields[field.field_name] = {"type": "string", "__example__": ""}

		return screen_data_map

	def build_screen(self, screen, incoming_data=None):
		screen_data = {
			"id": screen.screen_id,
			"title": screen.screen_title,
			"data": incoming_data or {},
			"layout": {"type": "SingleColumnLayout", "children": []},
		}

		if screen.terminal:
			screen_data["terminal"] = True
			screen_data["success"] = True

		if screen.refresh_on_back:
			screen_data["refresh_on_back"] = True

		children = self.build_screen_fields(screen)
		screen_data["layout"]["children"] = children

		return screen_data

	def build_screen_fields(self, screen):
		children = []
		has_footer = False

		for field in self.fields:
			if field.screen != screen.screen_id:
				continue
			if not field.enabled:
				continue

			component = self.build_field_component(field, screen)
			if component:
				children.append(component)
				if field.field_type == "Footer":
					has_footer = True

		if not has_footer:
			footer_action = self.build_footer_action(None, screen)
			children.append(
				{
					"type": "Footer",
					"label": "Continue" if not screen.terminal else "Complete",
					"on-click-action": footer_action,
				}
			)

		return children

	def build_field_component(self, field, screen):
		field_type = field.field_type

		if field_type in ["TextHeading", "TextSubheading", "TextBody", "TextCaption"]:
			return {"type": field_type, "text": field.label or ""}

		if field_type == "Image":
			component = {"type": "Image", "src": field.init_value or ""}
			if field.label:
				component["alt-text"] = field.label
			return component

		if field_type == "EmbeddedLink":
			return {
				"type": "EmbeddedLink",
				"text": field.label or "Link",
				"on-click-action": {
					"name": "navigate",
					"next": {"type": "screen", "name": field.init_value or ""},
				},
			}

		if field_type == "Footer":
			action = self.build_footer_action(field, screen)
			return {"type": "Footer", "label": field.label or "Submit", "on-click-action": action}

		component = {"type": field_type, "name": field.field_name, "label": field.label or field.field_name}

		if field.required:
			component["required"] = True

		if field.helper_text:
			component["helper-text"] = field.helper_text

		if field.init_value:
			component["init-value"] = field.init_value

		if field_type in ["TextInput", "TextArea"]:
			if field.min_chars:
				component["min-chars"] = field.min_chars
			if field.max_chars:
				component["max-chars"] = field.max_chars
			if field.error_message:
				component["error-message"] = field.error_message

		if field_type in ["Dropdown", "RadioButtonsGroup", "CheckboxGroup"]:
			options = self.parse_options(field.options)
			if options:
				component["data-source"] = options

		if field_type == "OptIn":
			component["label"] = field.label or "I agree"
			if field.required:
				component["required"] = True

		return component

	def build_footer_action(self, field, screen):
		if screen.terminal:
			return {"name": "complete", "payload": self.build_payload(screen)}
		else:
			next_screen = self.get_next_screen(screen)
			if next_screen:
				return {
					"name": "navigate",
					"next": {"type": "screen", "name": next_screen.screen_id},
					"payload": self.build_payload(screen),
				}
			else:
				return {"name": "complete", "payload": self.build_payload(screen)}

	def build_payload(self, screen):
		payload = {}

		for s in self.screens:
			if s.screen_id == screen.screen_id:
				for field in self.fields:
					if field.screen != s.screen_id:
						continue
					if field.enabled and field.field_type not in [
						"TextHeading",
						"TextSubheading",
						"TextBody",
						"TextCaption",
						"Image",
						"EmbeddedLink",
						"Footer",
					]:
						payload[field.field_name] = "${form." + field.field_name + "}"
				break
			else:
				for field in self.fields:
					if field.screen != s.screen_id:
						continue
					if field.enabled and field.field_type not in [
						"TextHeading",
						"TextSubheading",
						"TextBody",
						"TextCaption",
						"Image",
						"EmbeddedLink",
						"Footer",
					]:
						payload[field.field_name] = "${data." + field.field_name + "}"

		return payload

	def get_next_screen(self, current_screen):
		found_current = False
		for screen in self.screens:
			if found_current:
				return screen
			if screen.screen_id == current_screen.screen_id:
				found_current = True
		return None

	def parse_options(self, options_json):
		if not options_json:
			return []
		try:
			options = json.loads(options_json)
			if isinstance(options, list):
				return options
			return []
		except json.JSONDecodeError:
			return []

	@frappe.whitelist(methods=["POST"])
	def create_on_whatsapp(self):
		require_admin()
		require("WhatsApp Flow", "write")
		if self.flow_id:
			frappe.throw(_("Flow already exists on WhatsApp. Use update instead."))

		account = frappe.get_doc("OneChat Account", self.whatsapp_account)
		token = account.get_password("token")

		url = f"{account.url}/{account.version}/{account.business_id}/flows"

		payload = {"name": self.flow_name, "categories": [self.category]}

		headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

		try:
			response = make_post_request(url, headers=headers, data=json.dumps(payload))
		except Exception as e:
			frappe.throw(_("Failed to create flow: {0}").format(str(e)))

		self.flow_id = response.get("id")
		self.save()
		frappe.db.commit()

		try:
			self.upload_flow_json()
		except Exception as e:
			frappe.msgprint(
				_(
					"Flow created on WhatsApp, but uploading its screens failed: {0}. Upload again after fixing it."
				).format(str(e)),
				indicator="orange",
			)
			return

		frappe.msgprint(_("Flow created successfully on WhatsApp"))

	@frappe.whitelist()
	def upload_flow_json(self):
		require_admin()
		require("WhatsApp Flow", "write")
		if not self.flow_id:
			frappe.throw(_("Flow must be created on WhatsApp first"))

		account = frappe.get_doc("OneChat Account", self.whatsapp_account)
		token = account.get_password("token")

		url = f"{account.url}/{account.version}/{self.flow_id}/assets"

		flow_json = self.generate_flow_json()

		headers = {"Authorization": f"Bearer {token}"}

		files = {
			"file": ("flow.json", json.dumps(flow_json), "application/json"),
			"name": (None, "flow.json"),
			"asset_type": (None, "FLOW_JSON"),
		}

		try:
			import requests

			response = requests.post(url, headers=headers, files=files)

			if response.status_code != 200:
				error_data = response.json()
				error_msg = error_data.get("error", {}).get("message", response.text)
				error_details = error_data.get("error", {}).get("error_user_msg", "")
				if error_details:
					error_msg = f"{error_msg} - {error_details}"
				frappe.throw(_("Failed to upload flow JSON: {0}").format(error_msg))

			frappe.msgprint(_("Flow JSON uploaded successfully"))

		except requests.exceptions.RequestException as e:
			frappe.throw(_("Failed to upload flow JSON: {0}").format(str(e)))

	@frappe.whitelist()
	def publish_flow(self):
		require_admin()
		require("WhatsApp Flow", "write")
		if not self.flow_id:
			frappe.throw(_("Flow must be created on WhatsApp first"))

		if self.status == "Published":
			frappe.throw(_("Flow is already published"))

		account = frappe.get_doc("OneChat Account", self.whatsapp_account)
		token = account.get_password("token")

		url = f"{account.url}/{account.version}/{self.flow_id}/publish"

		headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

		try:
			import requests

			response = requests.post(url, headers=headers)

			if response.status_code != 200:
				error_data = response.json()
				error_msg = error_data.get("error", {}).get("message", response.text)
				frappe.throw(_("Failed to publish flow: {0}").format(error_msg))

			self.status = "Published"
			self.save()

			frappe.msgprint(_("Flow published successfully"))

		except Exception as e:
			frappe.throw(_("Failed to publish flow: {0}").format(str(e)))

	@frappe.whitelist()
	def deprecate_flow(self):
		require_admin()
		require("WhatsApp Flow", "write")
		if not self.flow_id:
			frappe.throw(_("Flow must be created on WhatsApp first"))

		account = frappe.get_doc("OneChat Account", self.whatsapp_account)
		token = account.get_password("token")

		url = f"{account.url}/{account.version}/{self.flow_id}/deprecate"

		headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

		try:
			make_post_request(url, headers=headers)
			self.status = "Deprecated"
			self.save()

			frappe.msgprint(_("Flow deprecated successfully"))

		except Exception as e:
			frappe.throw(_("Failed to deprecate flow: {0}").format(str(e)))

	@frappe.whitelist()
	def delete_from_whatsapp(self):
		require_admin()
		require("WhatsApp Flow", "delete")
		if not self.flow_id:
			frappe.throw(_("Flow does not exist on WhatsApp"))

		account = frappe.get_doc("OneChat Account", self.whatsapp_account)
		token = account.get_password("token")

		url = f"{account.url}/{account.version}/{self.flow_id}"

		headers = {"Authorization": f"Bearer {token}"}

		try:
			import requests

			response = requests.delete(url, headers=headers)
			response.raise_for_status()

			self.flow_id = None
			self.status = "Draft"
			self.save()

			frappe.msgprint(_("Flow deleted from WhatsApp"))

		except Exception as e:
			frappe.throw(_("Failed to delete flow: {0}").format(str(e)))

	@frappe.whitelist()
	def get_flow_preview(self):
		require_admin()
		if not self.flow_id:
			frappe.throw(_("Flow must be created on WhatsApp first"))

		account = frappe.get_doc("OneChat Account", self.whatsapp_account)
		token = account.get_password("token")

		url = f"{account.url}/{account.version}/{self.flow_id}?fields=preview.invalidate(false)"

		headers = {"Authorization": f"Bearer {token}"}

		try:
			import requests

			response = requests.get(url, headers=headers)
			response.raise_for_status()

			data = response.json()
			preview_url = data.get("preview", {}).get("preview_url")

			if preview_url:
				self.db_set("preview_url", preview_url)
				return preview_url

			frappe.throw(_("Preview URL not available"))

		except Exception as e:
			frappe.throw(_("Failed to get preview: {0}").format(str(e)))

	@frappe.whitelist(methods=["POST"])
	def send_test(self, phone_number: str | int, message: str | None = None):
		require_admin()
		require("OneChat Message", "create")
		if not self.flow_id:
			frappe.throw(_("Flow must be created on WhatsApp first"))

		msg = frappe.get_doc(
			{
				"doctype": "OneChat Message",
				"type": "Outgoing",
				"to": phone_number,
				"content_type": "flow",
				"flow": self.name,
				"flow_cta": self.flow_cta or "Open Form",
				"message": message or f"Test: {self.flow_name}",
				"whatsapp_account": self.whatsapp_account,
			}
		)
		msg.insert(ignore_permissions=True)
		frappe.db.commit()

		frappe.msgprint(_("Test flow sent to {0}").format(phone_number), indicator="green")
		return msg.name

	@frappe.whitelist()
	def get_flow_status(self):
		require_admin()
		if not self.flow_id:
			frappe.throw(_("Flow must be created on WhatsApp first"))

		account = frappe.get_doc("OneChat Account", self.whatsapp_account)
		token = account.get_password("token")

		url = f"{account.url}/{account.version}/{self.flow_id}?fields=id,name,status,categories,validation_errors,json_version,data_api_version,data_channel_uri,preview,whatsapp_business_account"

		headers = {"Authorization": f"Bearer {token}"}

		try:
			import requests

			response = requests.get(url, headers=headers)
			response.raise_for_status()

			data = response.json()

			if data.get("status"):
				self.status = data["status"].title()
				self.save()

			validation_errors = data.get("validation_errors", [])
			if validation_errors:
				error_messages = []
				for error in validation_errors:
					error_messages.append(
						f"- {error.get('error', 'Unknown error')} at {error.get('error_type', 'unknown')}"
					)
				frappe.msgprint(
					"<br>".join([_("Flow validation errors:"), *error_messages]),
					title=_("Validation Errors"),
					indicator="red",
				)
			else:
				frappe.msgprint(
					"<br>".join(
						[
							_("Flow status: {0}").format(data.get("status") or _("Unknown")),
							_("JSON version: {0}").format(data.get("json_version") or _("Unknown")),
						]
					),
					title=_("Flow Status"),
					indicator="green" if data.get("status") == "PUBLISHED" else "blue",
				)

			return data

		except Exception as e:
			frappe.throw(_("Failed to get flow status: {0}").format(str(e)))

	@frappe.whitelist()
	def sync_from_whatsapp(self):
		require_admin()
		require("WhatsApp Flow", "write")
		if not self.flow_id:
			frappe.throw(_("Flow ID is required to sync"))

		account = frappe.get_doc("OneChat Account", self.whatsapp_account)
		token = account.get_password("token")

		url = f"{account.url}/{account.version}/{self.flow_id}?fields=id,name,status,categories,json_version,preview"

		headers = {"Authorization": f"Bearer {token}"}

		try:
			import requests

			response = requests.get(url, headers=headers)
			response.raise_for_status()

			data = response.json()

			if data.get("status"):
				self.status = data["status"].title()
			if data.get("categories"):
				self.category = data["categories"][0] if data["categories"] else "OTHER"
			if data.get("json_version"):
				self.data_api_version = data["json_version"]
			if data.get("preview", {}).get("preview_url"):
				self.preview_url = data["preview"]["preview_url"]

			flow_json = self.fetch_flow_json()
			if flow_json:
				self.flow_json = json.dumps(flow_json, indent=2)

			self.save()
			frappe.msgprint(_("Flow synced successfully from WhatsApp"), indicator="green")

			return data

		except Exception as e:
			frappe.throw(_("Failed to sync flow: {0}").format(str(e)))

	def fetch_flow_json(self):
		if not self.flow_id:
			return None

		account = frappe.get_doc("OneChat Account", self.whatsapp_account)
		token = account.get_password("token")

		url = f"{account.url}/{account.version}/{self.flow_id}/assets"

		headers = {"Authorization": f"Bearer {token}"}

		try:
			import requests

			response = requests.get(url, headers=headers)
			response.raise_for_status()

			data = response.json()
			assets = data.get("data", [])

			for asset in assets:
				if asset.get("name") == "flow.json":
					download_url = asset.get("download_url")
					if download_url:
						asset_response = requests.get(download_url, headers=headers)
						if asset_response.status_code == 200:
							return asset_response.json()

			return None

		except Exception as e:
			frappe.log_error(f"Failed to fetch flow JSON: {e!s}")
			return None


@frappe.whitelist()
def get_whatsapp_flows(whatsapp_account: str):
	require_admin()
	account = frappe.get_doc("OneChat Account", whatsapp_account)
	token = account.get_password("token")

	url = f"{account.url}/{account.version}/{account.business_id}/flows?fields=id,name,status,categories"

	headers = {"Authorization": f"Bearer {token}"}

	try:
		import requests

		response = requests.get(url, headers=headers)
		response.raise_for_status()

		data = response.json()
		flows = data.get("data", [])

		for flow in flows:
			existing = frappe.db.exists("WhatsApp Flow", {"flow_id": flow["id"]})
			flow["exists_locally"] = bool(existing)
			flow["local_name"] = existing if existing else None

		return flows

	except Exception as e:
		frappe.throw(_("Failed to fetch flows: {0}").format(str(e)))


@frappe.whitelist()
def import_flow_from_whatsapp(whatsapp_account: str, flow_id: str, flow_name: str | None = None):
	require_admin()
	require("WhatsApp Flow", "create")
	return import_flow(whatsapp_account, flow_id, flow_name)


def import_flow(whatsapp_account, flow_id, flow_name=None):
	existing = frappe.db.exists("WhatsApp Flow", {"flow_id": flow_id})
	if existing:
		frappe.throw(_("Flow already exists: {0}").format(existing))

	account = frappe.get_doc("OneChat Account", whatsapp_account)
	token = account.get_password("token")

	url = f"{account.url}/{account.version}/{flow_id}?fields=id,name,status,categories,json_version,preview"

	headers = {"Authorization": f"Bearer {token}"}

	try:
		import requests

		response = requests.get(url, headers=headers)
		response.raise_for_status()

		data = response.json()

		flow_doc = frappe.get_doc(
			{
				"doctype": "WhatsApp Flow",
				"flow_name": flow_name or data.get("name", f"Imported Flow {flow_id}"),
				"whatsapp_account": whatsapp_account,
				"flow_id": flow_id,
				"status": data.get("status", "Draft").title(),
				"category": data["categories"][0] if data.get("categories") else "OTHER",
				"data_api_version": data.get("json_version", "6.0"),
				"preview_url": data.get("preview", {}).get("preview_url", ""),
			}
		)

		flow_json = fetch_flow_json_by_id(whatsapp_account, flow_id)
		if flow_json:
			flow_doc.flow_json = json.dumps(flow_json, indent=2)
			parse_flow_json_to_screens(flow_doc, flow_json)

		flow_doc.flags.ignore_validate = True
		flow_doc.insert(ignore_permissions=True)

		frappe.db.commit()
		frappe.msgprint(_("Flow imported successfully: {0}").format(flow_doc.name), indicator="green")

		return flow_doc.name

	except Exception as e:
		frappe.throw(_("Failed to import flow: {0}").format(str(e)))


def fetch_flow_json_by_id(whatsapp_account, flow_id):
	account = frappe.get_doc("OneChat Account", whatsapp_account)
	token = account.get_password("token")

	url = f"{account.url}/{account.version}/{flow_id}/assets"

	headers = {"Authorization": f"Bearer {token}"}

	try:
		import requests

		response = requests.get(url, headers=headers)
		response.raise_for_status()

		data = response.json()
		assets = data.get("data", [])

		for asset in assets:
			if asset.get("name") == "flow.json":
				download_url = asset.get("download_url")
				if download_url:
					asset_response = requests.get(download_url, headers=headers)
					if asset_response.status_code == 200:
						return asset_response.json()

		return None

	except Exception as e:
		frappe.log_error(f"Failed to fetch flow JSON: {e!s}")
		return None


@frappe.whitelist(methods=["POST"])
def sync_all_flows(whatsapp_account: str):
	require_admin()
	require("WhatsApp Flow", "create")
	account = frappe.get_doc("OneChat Account", whatsapp_account)
	token = account.get_password("token")

	url = f"{account.url}/{account.version}/{account.business_id}/flows?fields=id,name,status,categories"

	headers = {"Authorization": f"Bearer {token}"}

	result = {"imported": 0, "updated": 0, "skipped": 0}

	try:
		import requests

		response = requests.get(url, headers=headers)
		response.raise_for_status()

		data = response.json()
		flows = data.get("data", [])

		frappe.log_error(title="flows", message=flows)

		for flow in flows:
			flow_id = flow.get("id")
			flow_name = flow.get("name")

			existing = frappe.db.exists("WhatsApp Flow", {"flow_id": flow_id})

			if existing:
				try:
					flow_doc = frappe.get_doc("WhatsApp Flow", existing)
					flow_doc.status = flow.get("status", "Draft").title()
					if flow.get("categories"):
						flow_doc.category = flow["categories"][0]

					flow_json = fetch_flow_json_by_id(whatsapp_account, flow_id)

					if flow_json:
						flow_doc.flow_json = json.dumps(flow_json, indent=2)
						flow_doc.data_api_version = flow_json.get("version", "6.0")

						flow_doc.screens = []
						flow_doc.fields = []
						parse_flow_json_to_screens(flow_doc, flow_json)

					flow_doc.flags.ignore_validate = True
					flow_doc.save(ignore_permissions=True)
					result["updated"] += 1
				except Exception as e:
					frappe.log_error(f"Failed to update flow {flow_id}: {e!s}")
					result["skipped"] += 1
			else:
				try:
					flow_doc = frappe.get_doc(
						{
							"doctype": "WhatsApp Flow",
							"flow_name": flow_name or f"Flow {flow_id}",
							"whatsapp_account": whatsapp_account,
							"flow_id": flow_id,
							"status": flow.get("status", "Draft").title(),
							"category": flow["categories"][0] if flow.get("categories") else "OTHER",
						}
					)

					flow_json = fetch_flow_json_by_id(whatsapp_account, flow_id)
					if flow_json:
						flow_doc.flow_json = json.dumps(flow_json, indent=2)
						flow_doc.data_api_version = flow_json.get("version", "6.0")
						parse_flow_json_to_screens(flow_doc, flow_json)

					flow_doc.flags.ignore_validate = True
					flow_doc.insert(ignore_permissions=True)
					result["imported"] += 1
				except Exception as e:
					frappe.log_error(f"Failed to import flow {flow_id}: {e!s}")
					result["skipped"] += 1

		frappe.db.commit()
		return result

	except Exception as e:
		frappe.throw(_("Failed to sync flows: {0}").format(str(e)))


def parse_flow_json_to_screens(flow_doc, flow_json):
	screens = flow_json.get("screens", [])

	for screen_data in screens:
		flow_doc.append(
			"screens",
			{
				"screen_id": screen_data.get("id"),
				"screen_title": screen_data.get("title", ""),
				"terminal": 1 if screen_data.get("terminal") else 0,
				"refresh_on_back": 1 if screen_data.get("refresh_on_back") else 0,
			},
		)

		layout = screen_data.get("layout", {})
		children = layout.get("children", [])

		for child in children:
			field_type = child.get("type")
			if not field_type:
				continue

			field_data = {
				"screen": screen_data.get("id"),
				"field_type": field_type,
				"field_name": child.get("name", field_type.lower()),
				"label": child.get("label") or child.get("text", ""),
				"required": 1 if child.get("required") else 0,
				"enabled": 1,
				"helper_text": child.get("helper-text", ""),
				"init_value": child.get("init-value", ""),
				"min_chars": child.get("min-chars"),
				"max_chars": child.get("max-chars"),
				"error_message": child.get("error-message", ""),
			}

			if field_type in ["Dropdown", "RadioButtonsGroup", "CheckboxGroup"]:
				data_source = child.get("data-source", [])
				if data_source:
					field_data["options"] = json.dumps(data_source)

			flow_doc.append("fields", field_data)
