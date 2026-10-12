import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.query_builder.functions import IfNull
from frappe.utils import add_to_date, cint, get_datetime, now, now_datetime
from pypika.terms import Field


class BulkWhatsAppMessage(Document):
	def autoname(self):
		self.name = make_autoname("BULK-WA-.YY.-.###")

	def validate_message(self):
		if not self.message_content:
			frappe.throw(_("Message content is required"))

	def validate_recipients(self):
		if self.recipient_type == "Segment":
			if not self.segment:
				frappe.throw(_("Choose a segment to send to"))
			from onechat.inbox.segments import recipients

			self.recipient_count = len(recipients(self.segment))
			if not self.recipient_count:
				frappe.throw(_("No subscribed contacts match this segment right now"))
			return

		if not self.recipients and not self.recipient_list:
			frappe.throw(_("At least one recipient or a recipient list is required"))

		if self.recipient_type == "Recipient List" and self.recipient_list:
			recipient_count = frappe.db.count("WhatsApp Recipient", {"parent": self.recipient_list})
			if recipient_count == 0:
				frappe.throw(_("Selected recipient list has no recipients"))
			self.recipient_count = recipient_count
		elif self.recipients:
			self.recipient_count = len(self.recipients)

	def on_submit(self):
		self.db_set("status", "Queued")
		self.queue_messages()

	def on_cancel(self):
		if self.get("smart_queue"):
			self.db_set("smart_queue", None)

	def validate(self):
		from onechat.inbox.accounts import require_whatsapp

		require_whatsapp(self.whatsapp_account)
		self.set_account()
		self.validate_recipients()
		self.validate_ab_test()

	def set_account(self):
		if not self.meta.has_field("whatsapp_account"):
			return
		if not self.whatsapp_account:
			from onechat.inbox.accounts import default_outgoing

			self.whatsapp_account = default_outgoing()
		for template in {self.get("template"), self.get("template_b")} - {None, ""}:
			owner = frappe.db.get_value("WhatsApp Templates", template, "whatsapp_account")
			if owner and self.whatsapp_account and owner != self.whatsapp_account:
				frappe.throw(
					frappe._(
						"Template {0} belongs to the number {1}. Pick a template of {2}, or send from {1}."
					).format(frappe.bold(template), frappe.bold(owner), frappe.bold(self.whatsapp_account))
				)

	def validate_ab_test(self):
		if not cint(self.ab_test):
			return
		if cint(self.get("smart_send")):
			frappe.throw(_("Smart send time can't be combined with an A/B test"))
		if not self.use_template or not self.template or not self.template_b:
			frappe.throw(_("An A/B test needs two approved templates"))
		if self.template_b == self.template:
			frappe.throw(_("Pick a different template for B"))
		if not 5 <= cint(self.ab_test_percent) <= 50:
			frappe.throw(_("The test group must be between 5% and 50% of recipients"))
		if cint(self.ab_wait_hours) < 1 or cint(self.ab_wait_hours) > 72:
			frappe.throw(_("Decide after 1 to 72 hours"))
		if cint(self.recipient_count) < 20:
			frappe.throw(_("A/B tests need at least 20 recipients"))

	def all_recipients(self):
		if self.recipient_type == "Segment" and self.segment:
			from onechat.inbox.segments import recipients

			return recipients(self.segment)
		if self.recipient_type == "Recipient List" and self.recipient_list:
			return frappe.get_all(
				"WhatsApp Recipient",
				filters={"parent": self.recipient_list},
				fields=["mobile_number", "name", "recipient_name", "recipient_data"],
			)
		return [
			{
				"mobile_number": row.mobile_number,
				"recipient_name": row.recipient_name,
				"recipient_data": row.recipient_data,
			}
			for row in self.recipients
		]

	def enqueue_recipient(self, recipient, variant=None):
		frappe.enqueue_doc(
			self.doctype,
			self.name,
			"create_single_message",
			"long",
			4000,
			recipient=dict(recipient),
			variant=variant,
			enqueue_after_commit=True,
		)

	def queue_messages(self):
		members = [dict(row) for row in self.all_recipients()]
		self.db_set("recipient_count", len(members))
		if not members:
			self.db_set("status", "Completed")
			return

		if cint(self.get("smart_send")):
			from onechat.campaigns.smart_send import plan

			now_rows, buckets = plan(members)
			for recipient in now_rows:
				self.enqueue_recipient(recipient)
			if buckets:
				self.db_set("smart_queue", json.dumps(buckets, default=str))
			return

		if not cint(self.ab_test):
			for recipient in members:
				self.enqueue_recipient(recipient)
			return

		from onechat.campaigns.ab_test import split

		group_a, group_b, rest = split(members, cint(self.ab_test_percent), self.name)
		self.db_set(
			{
				"ab_status": "Testing",
				"ab_decide_at": add_to_date(now_datetime(), hours=cint(self.ab_wait_hours) or 4),
				"ab_remaining": json.dumps(rest, default=str),
				"ab_winner": None,
			}
		)
		for recipient in group_a:
			self.enqueue_recipient(recipient, "A")
		for recipient in group_b:
			self.enqueue_recipient(recipient, "B")

	def body_values(self, recipient):
		mapping = parse_data(self.template_variables)
		if not mapping:
			return None
		data = parse_data(recipient.get("recipient_data"))
		data.setdefault("recipient_name", recipient.get("recipient_name"))
		data.setdefault("mobile_number", recipient.get("mobile_number"))
		values = []
		for index, source in enumerate(mapping.values()):
			text = "" if source is None else str(source)
			if text.startswith("recipient."):
				key = text[len("recipient.") :]
				value = data.get(key)
				if value in (None, ""):
					value = data.get(key.strip().lower().replace(" ", "_"))
				if value in (None, "") and index == 0:
					value = data.get("recipient_name")
				text = "" if value is None else str(value)
			values.append(text)
		return json.dumps({str(position): value for position, value in enumerate(values, start=1)})

	def create_single_message(self, recipient, variant=None):
		from onechat.inbox.consent import OptedOutError, is_opted_out

		number = recipient.get("mobile_number")
		if is_opted_out(number):
			self.bump("skipped_count")
			self.finish()
			return

		wa_message = frappe.new_doc("OneChat Message")
		wa_message.type = "Outgoing"
		wa_message.to = number
		wa_message.message_type = "Manual"
		wa_message.flags.custom_ref_doc = parse_data(recipient.get("recipient_data"))
		wa_message.bulk_message_reference = self.name
		wa_message.source = "Broadcast"
		if self.get("whatsapp_account"):
			wa_message.whatsapp_account = self.whatsapp_account
		if variant:
			wa_message.ab_variant = variant

		if self.use_template:
			wa_message.template = self.template_b if variant == "B" and self.template_b else self.template
			wa_message.message_type = "Template"
			wa_message.use_template = self.use_template
			body = self.body_values(recipient)
			if body:
				wa_message.body_param = body

		wa_message.status = "Queued"
		try:
			wa_message.insert(ignore_permissions=True)
		except OptedOutError:
			frappe.clear_messages()
			self.bump("skipped_count")
			self.finish()
			return
		except Exception:
			frappe.log_error(title="WhatsApp Bulk Messaging")
			frappe.db.set_value(self.doctype, self.name, "status", "Partially Failed")

		self.bump("sent_count")
		self.finish()

	def bump(self, field):
		table = frappe.qb.DocType(self.doctype)
		column = Field(field, table=table)
		(frappe.qb.update(table).set(column, IfNull(column, 0) + 1).where(table.name == self.name).run())

	def finish(self):
		row = frappe.db.get_value(
			self.doctype,
			self.name,
			["recipient_count", "sent_count", "skipped_count", "status"],
			as_dict=True,
		)
		if row.status == "Partially Failed":
			return
		if (
			cint(row.sent_count) + cint(row.skipped_count) >= cint(row.recipient_count)
			and row.status != "Completed"
		):
			frappe.db.set_value(self.doctype, self.name, "status", "Completed")
			from onechat.workspace.webhooks import BULK, fire

			fire(self.name, "completed", BULK)

	def retry_failed(self):
		failed_messages = frappe.get_all(
			"OneChat Message",
			filters={"bulk_message_reference": self.name, "status": "Failed"},
			fields=["name"],
		)

		count = 0
		for msg in failed_messages:
			message_doc = frappe.get_doc("OneChat Message", msg.name)
			message_doc.status = "Queued"
			message_doc.save(ignore_permissions=True)
			count += 1

		frappe.msgprint(_("{0} messages have been requeued for sending").format(count))

	def get_progress(self):
		total = self.recipient_count
		sent = frappe.db.count(
			"OneChat Message",
			{"bulk_message_reference": self.name, "status": ["in", ["sent", "delivered", "Success", "read"]]},
		)
		failed = frappe.db.count("OneChat Message", {"bulk_message_reference": self.name, "status": "Failed"})
		queued = frappe.db.count("OneChat Message", {"bulk_message_reference": self.name, "status": "Queued"})

		return {
			"total": total,
			"sent": sent,
			"failed": failed,
			"queued": queued,
			"skipped": cint(self.skipped_count),
			"percent": (sent / total * 100) if total else 0,
		}


def parse_data(value):
	try:
		return json.loads(value or "{}")
	except Exception:
		return {}
