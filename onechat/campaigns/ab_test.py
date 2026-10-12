import json
import random

import frappe
from frappe import _
from frappe.query_builder.functions import Count, Lower, Min
from frappe.utils import cint, now_datetime

from onechat.workspace.session import require_admin

BULK = "Bulk WhatsApp Message"
MESSAGE = "OneChat Message"
READ = ("read",)
DELIVERED = ("delivered", "read")
FAILED = ("failed",)
MIN_GROUP = 5


def split(members, percent, seed):
	pool = list(members)
	random.Random(str(seed)).shuffle(pool)
	test = max(MIN_GROUP * 2, round(len(pool) * max(5, min(50, cint(percent))) / 100))
	test = min(test - test % 2, len(pool) - len(pool) % 2)
	group = pool[:test]
	return group[0::2], group[1::2], pool[test:]


def variant_stats(name):
	message = frappe.qb.DocType(MESSAGE)
	out = {
		variant: {
			"sent": 0,
			"delivered": 0,
			"read": 0,
			"failed": 0,
			"replied": 0,
			"first_sent": None,
		}
		for variant in ("A", "B")
	}
	for variant, status, count, first in (
		frappe.qb.from_(message)
		.select(message.ab_variant, Lower(message.status), Count("*"), Min(message.creation))
		.where((message.bulk_message_reference == name) & message.ab_variant.isin(["A", "B"]))
		.groupby(message.ab_variant, Lower(message.status))
		.run()
	):
		row = out[variant]
		row["sent"] += cint(count)
		if status in DELIVERED:
			row["delivered"] += cint(count)
		if status in READ:
			row["read"] += cint(count)
		if status in FAILED:
			row["failed"] += cint(count)
		if first and (not row["first_sent"] or first < row["first_sent"]):
			row["first_sent"] = first

	for variant, row in out.items():
		contacts = frappe.get_all(
			MESSAGE,
			filters={
				"bulk_message_reference": name,
				"ab_variant": variant,
				"whatsapp_contact": ["is", "set"],
			},
			pluck="whatsapp_contact",
			distinct=True,
			limit_page_length=0,
		)
		if contacts and row["first_sent"]:
			row["replied"] = cint(
				frappe.qb.from_(message)
				.select(Count(message.whatsapp_contact).distinct())
				.where(
					(message.type == "Incoming")
					& message.whatsapp_contact.isin(contacts)
					& (message.creation >= row["first_sent"])
				)
				.run()[0][0]
			)
		base = max(row["sent"] - row["failed"], 0)
		row["read_rate"] = round(row["read"] * 100 / base, 1) if base else 0
		row["reply_rate"] = round(row["replied"] * 100 / base, 1) if base else 0
		row["first_sent"] = str(row["first_sent"]) if row["first_sent"] else None
	return out


def pick_winner(stats, metric):
	first, second = ("reply_rate", "read_rate") if metric != "Reads" else ("read_rate", "reply_rate")
	a, b = stats["A"], stats["B"]
	return "B" if (b[first], b[second]) > (a[first], a[second]) else "A"


def send_rest(doc, winner):
	rest = json.loads(doc.ab_remaining or "[]")
	doc.db_set({"ab_winner": winner, "ab_status": "Done", "ab_remaining": None})
	for recipient in rest:
		doc.enqueue_recipient(recipient, winner)
	if not rest:
		doc.finish()
	return len(rest)


def decide(name, winner=None):
	doc = frappe.get_doc(BULK, name)
	if doc.ab_status != "Testing":
		return None
	winner = winner or pick_winner(variant_stats(name), doc.ab_metric)
	count = send_rest(doc, winner)
	notify(doc, winner, count)
	return winner


def notify(doc, winner, count):
	template = doc.template_b if winner == "B" else doc.template
	subject = _("{0}: version {1} ({2}) won and is going to {3} more recipients").format(
		doc.title or doc.name, winner, template, count
	)
	for user in {doc.owner, doc.modified_by} - {None, "Administrator", "Guest"}:
		frappe.get_doc(
			{
				"doctype": "Notification Log",
				"subject": subject,
				"for_user": user,
				"type": "Alert",
				"document_type": BULK,
				"document_name": doc.name,
			}
		).insert(ignore_permissions=True)


def run():
	for name in frappe.get_all(
		BULK,
		filters={
			"ab_status": "Testing",
			"ab_decide_at": ["<=", now_datetime()],
			"docstatus": 1,
		},
		pluck="name",
	):
		try:
			decide(name)
			frappe.db.commit()  # nosemgrep: frappe-manual-commit - commit A/B test decision per campaign
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title=f"OneChat A/B test: {name}")


@frappe.whitelist()
def results(name: str):
	require_admin()
	doc = frappe.get_doc(BULK, name)
	if not cint(doc.ab_test):
		return None
	stats = variant_stats(name)
	return {
		"status": doc.ab_status,
		"metric": doc.ab_metric or "Replies",
		"decide_at": str(doc.ab_decide_at) if doc.ab_decide_at else None,
		"winner": doc.ab_winner,
		"leader": pick_winner(stats, doc.ab_metric),
		"waiting": len(json.loads(doc.ab_remaining or "[]")),
		"templates": {"A": doc.template, "B": doc.template_b},
		"variants": stats,
	}


@frappe.whitelist(methods=["POST"])
def send_winner(name: str, winner: str | None = None):
	require_admin()
	if winner not in (None, "", "A", "B"):
		frappe.throw(_("Pick A or B."))
	result = decide(name, winner or None)
	if not result:
		frappe.throw(_("This test has already been decided."))
	return results(name)
