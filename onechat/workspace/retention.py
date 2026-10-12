import json

import frappe
from frappe import _
from frappe.utils import add_days, cint, now_datetime

from onechat.workspace.session import is_admin

SETTINGS = "OneChat Settings"
MESSAGE = "OneChat Message"
MIN_MESSAGE_DAYS = 30
MIN_MEDIA_DAYS = 7
BATCH = 500
MAX_PER_RUN = 20000
RECORDS = (
	{
		"key": "notification_logs",
		"doctype": "WhatsApp Notification Log",
		"filters": {"template": ["!=", "Webhook"]},
		"min": 7,
	},
	{
		"key": "flow_runs",
		"doctype": "Automation Execution Log",
		"filters": {"status": ["not in", ["Running", "Waiting"]]},
		"children": ("Automation Execution Step",),
		"min": 7,
	},
	{
		"key": "flow_sessions",
		"doctype": "OneChat Flow Session",
		"filters": {"status": ["in", ["Completed", "Stopped", "Failed", "Expired"]]},
		"min": 7,
	},
	{
		"key": "reminders",
		"doctype": "OneChat Reminder",
		"filters": {"status": ["!=", "Pending"]},
		"min": 7,
	},
	{
		"key": "contact_history",
		"doctype": "Version",
		"filters": {"ref_doctype": "OneChat Contact"},
		"min": 90,
	},
)


def admin_only():
	if not is_admin():
		frappe.throw(_("Only OneChat admins can manage data retention."), frappe.PermissionError)


def record_days(settings):
	try:
		stored = json.loads(settings.get("retention_records") or "{}")
	except ValueError:
		stored = {}
	out = {}
	for spec in RECORDS:
		days = cint(stored.get(spec["key"])) if isinstance(stored, dict) else 0
		out[spec["key"]] = max(days, spec["min"]) if days > 0 else 0
	return out


def policy():
	settings = frappe.get_single(SETTINGS)
	return {
		"enabled": cint(settings.get("retention_enabled")),
		"message_days": max(cint(settings.get("message_retention_days")) or 365, MIN_MESSAGE_DAYS),
		"media_days": max(cint(settings.get("media_retention_days")) or 90, MIN_MEDIA_DAYS),
		"records": record_days(settings),
	}


def record_filters(spec, days):
	return {**spec["filters"], "creation": ["<", cutoff(days)]}


def purge_records(rules):
	out = {}
	for spec in RECORDS:
		days = rules["records"].get(spec["key"])
		if not days or not frappe.db.exists("DocType", spec["doctype"]):
			continue
		removed = 0
		while removed < MAX_PER_RUN:
			names = frappe.get_all(
				spec["doctype"], filters=record_filters(spec, days), pluck="name", limit_page_length=BATCH
			)
			if not names:
				break
			for child in spec.get("children", ()):
				frappe.db.delete(child, {"parenttype": spec["doctype"], "parent": ["in", names]})
			frappe.db.delete(spec["doctype"], {"name": ["in", names]})
			removed += len(names)
			frappe.db.commit()
		if removed:
			out[spec["key"]] = removed
	return out


def cutoff(days):
	return add_days(now_datetime(), -days)


def protected_files():
	urls = set()
	for doctype, field in (
		("OneChat Media", "file"),
		("OneChat Quick Reply", "attach"),
		("WhatsApp Templates", "sample"),
	):
		if frappe.db.exists("DocType", doctype):
			urls.update(frappe.get_all(doctype, filters={field: ["is", "set"]}, pluck=field))

	return urls


def old_messages(before, limit):
	return frappe.get_all(
		MESSAGE, filters={"creation": ["<", before]}, fields=["name", "attach"], limit_page_length=limit
	)


def old_media(before, limit):
	return frappe.get_all(
		MESSAGE,
		filters={"creation": ["<", before], "attach": ["is", "set"]},
		fields=["name", "attach"],
		limit_page_length=limit,
	)


def delete_files(urls, keep):
	removed = 0
	for url in {url for url in urls if url and url not in keep}:
		for name in frappe.get_all("File", filters={"file_url": url}, pluck="name"):
			try:
				frappe.delete_doc("File", name, ignore_permissions=True, force=True)
				removed += 1
			except Exception:
				frappe.log_error(title="OneChat retention: file")

	return removed


def purge(rules):
	keep = protected_files()
	messages = 0
	media = 0

	while messages < MAX_PER_RUN:
		rows = old_messages(cutoff(rules["message_days"]), BATCH)
		if not rows:
			break
		media += delete_files([row.attach for row in rows], keep)
		frappe.db.delete(MESSAGE, {"name": ["in", [row.name for row in rows]]})
		messages += len(rows)
		frappe.db.commit()

	cleared = 0
	while cleared < MAX_PER_RUN:
		rows = old_media(cutoff(rules["media_days"]), BATCH)
		if not rows:
			break
		media += delete_files([row.attach for row in rows], keep)
		table = frappe.qb.DocType(MESSAGE)
		frappe.qb.update(table).set(table.attach, None).where(
			table.name.isin([row.name for row in rows])
		).run()
		cleared += len(rows)
		frappe.db.commit()

	return {"messages": messages, "media": media, "records": purge_records(rules)}


def record(result):
	summary = _("Removed {0} messages and {1} media files").format(result["messages"], result["media"])
	others = sum(result.get("records", {}).values())
	if others:
		summary += _(", plus {0} older log and history records").format(others)
	frappe.db.set_single_value(
		SETTINGS, {"retention_last_run": now_datetime(), "retention_last_summary": summary}
	)
	frappe.db.commit()

	return summary


def run():
	rules = policy()
	if not rules["enabled"]:
		return

	try:
		record(purge(rules))
	except Exception:
		frappe.log_error(title="OneChat retention")


def run_forced():
	record(purge(policy()))


@frappe.whitelist()
def preview():
	admin_only()

	rules = policy()
	settings = frappe.get_single(SETTINGS)
	return {
		**rules,
		"messages": frappe.db.count(MESSAGE, {"creation": ["<", cutoff(rules["message_days"])]}),
		"media": frappe.db.count(
			MESSAGE, {"creation": ["<", cutoff(rules["media_days"])], "attach": ["is", "set"]}
		),
		"last_run": settings.get("retention_last_run"),
		"last_summary": settings.get("retention_last_summary"),
		"min_message_days": MIN_MESSAGE_DAYS,
		"min_media_days": MIN_MEDIA_DAYS,
		"records": [
			{
				"key": spec["key"],
				"days": rules["records"].get(spec["key"]) or 0,
				"min": spec["min"],
				"total": frappe.db.count(spec["doctype"], spec["filters"])
				if frappe.db.exists("DocType", spec["doctype"])
				else 0,
				"due": frappe.db.count(spec["doctype"], record_filters(spec, rules["records"][spec["key"]]))
				if rules["records"].get(spec["key"]) and frappe.db.exists("DocType", spec["doctype"])
				else 0,
			}
			for spec in RECORDS
		],
	}


@frappe.whitelist(methods=["POST"])
def run_now():
	admin_only()

	frappe.enqueue(
		"onechat.workspace.retention.run_forced", queue="long", timeout=3600, enqueue_after_commit=True
	)
	return _("Cleanup started. It runs in the background; refresh in a few minutes to see the result.")
