import frappe
import requests

ACCOUNT = "OneChat Account"
MESSAGE = "OneChat Message"
ON_OPEN = "When an agent opens the chat"
ON_ARRIVAL = "When a message arrives"
NEVER = "Never"
TIMEOUT = 15


def mode(account):
	if not account or not frappe.get_meta(ACCOUNT).has_field("read_receipts"):
		return NEVER
	return frappe.db.get_value(ACCOUNT, account, "read_receipts") or ON_OPEN


def on_message(doc, method=None):
	if (
		doc.type != "Incoming"
		or not doc.get("message_id")
		or doc.get("content_type") in ("reaction", "comment")
	):
		return
	if mode(doc.get("whatsapp_account")) == ON_ARRIVAL:
		queue(doc.whatsapp_account, doc.message_id)


def on_open(contact):
	rows = frappe.get_all(
		MESSAGE,
		filters={
			"whatsapp_contact": contact,
			"type": "Incoming",
			"message_id": ["is", "set"],
			"content_type": ["not in", ["reaction", "comment"]],
		},
		fields=["message_id", "whatsapp_account"],
		order_by="creation desc",
		limit_page_length=1,
	)
	if rows and mode(rows[0].whatsapp_account) == ON_OPEN:
		queue(rows[0].whatsapp_account, rows[0].message_id)


def queue(account, message_id):
	frappe.enqueue(
		"onechat.inbox.read_receipts.send",
		queue="short",
		job_id=f"onechat_read_{message_id}",
		deduplicate=True,
		enqueue_after_commit=True,
		account=account,
		message_id=message_id,
	)


def send(account, message_id):
	doc = frappe.get_doc(ACCOUNT, account)
	if doc.get("channel") == "Instagram":
		mark_seen(doc, message_id)
		return
	token = doc.get_password("token", raise_exception=False)
	if not token or not doc.phone_id:
		return
	try:
		response = requests.post(
			f"{doc.url}/{doc.version}/{doc.phone_id}/messages",
			json={"messaging_product": "whatsapp", "status": "read", "message_id": message_id},
			headers={"Authorization": f"Bearer {token}"},
			timeout=TIMEOUT,
		)
		if not response.ok:
			frappe.log_error(title="OneChat read receipt", message=response.text[:1000])
	except requests.RequestException:
		frappe.log_error(title="OneChat read receipt")


def mark_seen(account, message_id):
	from onechat.instagram import graph

	party = frappe.db.get_value(MESSAGE, {"message_id": message_id}, "from")
	if not party:
		return
	try:
		graph.send(account, {"recipient": {"id": party}, "sender_action": "mark_seen"})
	except (graph.GraphError, requests.RequestException):
		frappe.log_error(title="OneChat Instagram read receipt")
