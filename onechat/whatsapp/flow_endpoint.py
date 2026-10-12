import hashlib
import hmac
import json

import frappe
from frappe import _


@frappe.whitelist(allow_guest=True)
def handle_flow_request():
	try:
		if frappe.request.method == "GET":
			return {"status": "ok"}

		data = frappe.request.get_json()

		if not data:
			frappe.throw(_("No data received"))

		frappe.log_error(f"WhatsApp Flow Request:\n{json.dumps(data, indent=2)}", "WhatsApp Flow Endpoint")

		action = data.get("action")

		if action == "ping":
			return {"data": {"status": "active"}}

		if action == "INIT":
			flow_token = data.get("flow_token")
			screen_id = data.get("screen")

			return handle_init(flow_token, screen_id, data)

		if action == "data_exchange":
			return handle_data_exchange(data)

		if action == "BACK":
			return handle_back(data)

		return {"data": {}}

	except Exception as e:
		frappe.log_error(f"Flow endpoint error: {e!s}", "WhatsApp Flow Error")
		return {"data": {"error": str(e)}}


def handle_init(flow_token, screen_id, data):
	return {"screen": screen_id or "INIT", "data": {}}


def handle_data_exchange(data):
	flow_token = data.get("flow_token")
	screen = data.get("screen")
	form_data = data.get("data", {})

	if flow_token:
		save_flow_data(flow_token, screen, form_data)

	return {"data": {}}


def handle_back(data):
	return {"data": {}}


def save_flow_data(flow_token, screen, form_data):
	try:
		existing = frappe.db.exists("WhatsApp Flow Data", {"flow_token": flow_token})

		if existing:
			doc = frappe.get_doc("WhatsApp Flow Data", existing)
			current_data = json.loads(doc.data or "{}")
			current_data.update(form_data)
			doc.data = json.dumps(current_data)
			doc.last_screen = screen
			doc.save(ignore_permissions=True)
		else:
			frappe.log_error(
				f"Flow Token: {flow_token}\nScreen: {screen}\nData: {json.dumps(form_data)}",
				"WhatsApp Flow Data",
			)
	except Exception as e:
		frappe.log_error(f"save_flow_data error: {e!s}")


def verify_signature(payload, signature, app_secret):
	expected_signature = hmac.new(app_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()

	return hmac.compare_digest(signature, expected_signature)
