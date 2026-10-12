import json
from collections import Counter, defaultdict
from datetime import timedelta

import frappe
from frappe.query_builder.functions import Count
from frappe.utils import add_days, cint, get_datetime, now_datetime
from pypika.enums import DatePart
from pypika.functions import Extract
from pypika.terms import Field

from onechat.inbox.conversations import MESSAGE, digits

BULK = "Bulk WhatsApp Message"
LOOKBACK_DAYS = 90
MIN_MESSAGES = 2
CHUNK = 500


def sender_batches(numbers):
	numbers = [str(number) for number in numbers if number]
	variants = list({*numbers, *(digits(number) for number in numbers)} - {""})
	for start in range(0, len(variants), CHUNK):
		yield variants[start : start + CHUNK]


def preferred_hours(numbers):
	message = frappe.qb.DocType(MESSAGE)
	sender = Field("from", table=message)
	hour = Extract(DatePart.hour, message.creation)
	since = add_days(now_datetime(), -LOOKBACK_DAYS)
	hours = defaultdict(Counter)
	for batch in sender_batches(numbers):
		for row in (
			frappe.qb.from_(message)
			.select(sender.as_("sender"), hour.as_("hour"), Count("*").as_("count"))
			.where((message.type == "Incoming") & (message.creation >= since) & sender.isin(batch))
			.groupby(sender, hour)
			.run(as_dict=True)
		):
			hours[digits(row.sender)][cint(row.hour)] += cint(row.count)
	return {
		number: counter.most_common(1)[0][0]
		for number, counter in hours.items()
		if sum(counter.values()) >= MIN_MESSAGES
	}


def plan(recipients):
	now = now_datetime()
	this_hour = now.replace(minute=0, second=0, microsecond=0)
	best = preferred_hours([row.get("mobile_number") for row in recipients])
	now_rows, buckets = [], defaultdict(list)
	for row in recipients:
		hour = best.get(digits(row.get("mobile_number")))
		if hour is None:
			now_rows.append(row)
			continue
		at = this_hour.replace(hour=hour)
		if at < this_hour:
			at += timedelta(days=1)
		if at == this_hour:
			now_rows.append(row)
		else:
			buckets[at.strftime("%Y-%m-%d %H:%M:%S")].append(row)
	return now_rows, dict(buckets)


def release_due():
	for name in frappe.get_all(BULK, filters={"docstatus": 1, "smart_queue": ["is", "set"]}, pluck="name"):
		try:
			release(name)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title="Smart send release failed", reference_doctype=BULK, reference_name=name)


def release(name):
	now = now_datetime()
	queue = frappe.db.get_value(BULK, name, "smart_queue", for_update=True)
	buckets = json.loads(queue or "{}")
	due = sorted(key for key in buckets if get_datetime(key) <= now)
	if not due:
		return
	doc = frappe.get_doc(BULK, name)
	for key in due:
		for row in buckets.pop(key):
			doc.enqueue_recipient(row)
	doc.db_set("smart_queue", json.dumps(buckets, default=str) if buckets else None)


def pending(doc):
	if doc.docstatus != 1:
		return []
	buckets = json.loads(doc.get("smart_queue") or "{}")
	return [{"at": key, "count": len(rows)} for key, rows in sorted(buckets.items())]
