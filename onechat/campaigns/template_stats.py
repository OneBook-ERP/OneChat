from bisect import bisect_right
from datetime import date

import frappe
from frappe.query_builder.functions import Count, IfNull, Lower, Max
from frappe.utils import add_days, add_to_date, cint, get_datetime, getdate, now_datetime

from onechat.api_types import JSON
from onechat.campaigns.broadcasts import ensure_admin
from onechat.inbox.conversations import MESSAGE, digits

RANGES = (7, 30, 90, 365, 0)
DAILY_UP_TO = 90
MAX_MONTHS = 36
LIMIT = 5000


def window(days):
	days = cint(days) if cint(days) in RANGES else 30
	if not days:
		return 0, None

	return days, get_datetime(getdate(add_days(now_datetime(), 1 - days)))


def sent_filter(message, templates, start):
	condition = (message.type == "Outgoing") & message.template.isin(templates)
	return condition & (message.creation >= start) if start else condition


def status_rows(templates, start):
	message = frappe.qb.DocType(MESSAGE)
	status = Lower(IfNull(message.status, ""))
	return (
		frappe.qb.from_(message)
		.select(message.template, status.as_("status"), Count("*").as_("count"))
		.where(sent_filter(message, templates, start))
		.groupby(message.template, status)
		.run(as_dict=True)
	)


def tally(rows):
	counts = {"sent": 0, "delivered": 0, "read": 0, "failed": 0}
	for row in rows:
		count = cint(row.count)
		counts["sent"] += count
		if row.status in ("delivered", "read"):
			counts["delivered"] += count
		if row.status == "read":
			counts["read"] += count
		if row.status == "failed":
			counts["failed"] += count

	return counts


def rate(part, whole):
	return round(part * 100 / whole, 1) if whole else None


@frappe.whitelist()
def summary(templates: JSON, days: int | str = 30):
	ensure_admin()
	from onechat.workspace.session import require_read

	require_read("WhatsApp Templates")
	templates = frappe.parse_json(templates) or []
	if not templates:
		return {}

	days, start = window(days)
	grouped = {}
	for row in status_rows(templates, start):
		grouped.setdefault(row.template, []).append(row)

	out = {}
	for name in templates:
		counts = tally(grouped.get(name, []))
		out[name] = {**counts, "read_rate": rate(counts["read"], counts["sent"])}

	return out


@frappe.whitelist()
def stats(template: str, days: int | str = 30):
	ensure_admin()
	days, start = window(days)
	counts = tally(status_rows([template], start))

	filters = [[MESSAGE, "type", "=", "Outgoing"], [MESSAGE, "template", "=", template]]
	if start:
		filters.append([MESSAGE, "creation", ">=", start])
	sent = frappe.get_all(
		MESSAGE,
		filters=filters,
		fields=["name", "status", "whatsapp_contact", "to", "creation"],
		order_by="creation desc",
		limit_page_length=LIMIT,
	)
	replied = replies(sent)
	rows = timeline(sent, replied, days)

	return {
		**counts,
		"replied": len(replied),
		"sampled": len(sent),
		"truncated": len(sent) >= LIMIT,
		"days": days,
		"delivered_rate": rate(counts["delivered"], counts["sent"]),
		"read_rate": rate(counts["read"], counts["sent"]),
		"replied_rate": rate(len(replied), len(sent)),
		"failed_rate": rate(counts["failed"], counts["sent"]),
		"series": [row["sent"] for row in rows],
		"timeline": rows,
		"last_sent": last_sent(template),
	}


def last_sent(template):
	message = frappe.qb.DocType(MESSAGE)
	rows = (
		frappe.qb.from_(message)
		.select(Max(message.creation).as_("at"))
		.where((message.type == "Outgoing") & (message.template == template))
		.run(as_dict=True)
	)
	return rows[0].at if rows else None


def is_daily(days):
	return bool(days and days <= DAILY_UP_TO)


def buckets(rows, days):
	today = getdate(now_datetime())
	if is_daily(days):
		return [add_days(today, offset - days + 1) for offset in range(days)]

	if days:
		months = 12
	elif rows:
		first = getdate(min(row.creation for row in rows))
		months = min((today.year - first.year) * 12 + today.month - first.month + 1, MAX_MONTHS)
	else:
		months = 1

	out = []
	for offset in range(months - 1, -1, -1):
		index = today.year * 12 + today.month - 1 - offset
		out.append(date(index // 12, index % 12 + 1, 1))

	return out


def timeline(rows, replied, days):
	daily = is_daily(days)
	out = {
		start: {"date": start.isoformat(), "sent": 0, "delivered": 0, "read": 0, "replied": 0, "failed": 0}
		for start in buckets(rows, days)
	}
	for row in rows:
		day = getdate(row.creation)
		bucket = out.get(day if daily else day.replace(day=1))
		if not bucket:
			continue
		status = (row.status or "").lower()
		bucket["sent"] += 1
		if status in ("delivered", "read"):
			bucket["delivered"] += 1
		if status == "read":
			bucket["read"] += 1
		if status == "failed":
			bucket["failed"] += 1
		if row.name in replied:
			bucket["replied"] += 1

	return list(out.values())


def key(contact, number):
	return contact or digits(number)


def replies(sent):
	if not sent:
		return set()

	contacts = list({row.whatsapp_contact for row in sent if row.whatsapp_contact})
	numbers = list({digits(row.to) for row in sent if not row.whatsapp_contact and digits(row.to)})
	first = get_datetime(min(row.creation for row in sent))
	last = add_to_date(get_datetime(max(row.creation for row in sent)), hours=24)
	base = [
		[MESSAGE, "type", "=", "Incoming"],
		[MESSAGE, "creation", ">", first],
		[MESSAGE, "creation", "<=", last],
	]

	incoming = {}
	for field, values in (("whatsapp_contact", contacts), ("from", numbers)):
		if not values:
			continue
		for row in frappe.get_all(
			MESSAGE,
			filters=[*base, [MESSAGE, field, "in", values]],
			fields=["whatsapp_contact", "from", "creation"],
			order_by="creation asc",
			limit_page_length=LIMIT * 4,
		):
			name = row.whatsapp_contact if field == "whatsapp_contact" else digits(row.get("from"))
			incoming.setdefault(name, []).append(get_datetime(row.creation))

	for times in incoming.values():
		times.sort()

	out = set()
	for row in sent:
		times = incoming.get(key(row.whatsapp_contact, row.to))
		if not times:
			continue
		at = get_datetime(row.creation)
		index = bisect_right(times, at)
		if index < len(times) and times[index] <= add_to_date(at, hours=24):
			out.add(row.name)

	return out
