import json
import re
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta
from statistics import median

import frappe
from frappe import _
from frappe.query_builder import Case, Order
from frappe.query_builder.functions import Avg, Count, IfNull, Lower, Sum
from frappe.utils import cint, flt, get_datetime, get_fullname, getdate, now_datetime
from pypika.enums import DatePart
from pypika.functions import Date, Extract

from onechat.workspace import numbers
from onechat.workspace.session import require_admin

MESSAGE = "OneChat Message"
CONTACT = "OneChat Contact"
CONVERSATION = "OneChat Conversation"
SESSION = "OneChat Flow Session"
FLOW = "OneChat Flow"
RUN_LOG = "Automation Execution Log"
TEMPLATE = "WhatsApp Templates"
BROADCAST = "Bulk WhatsApp Message"
AGENT = "OneChat User"
TEAM = "OneChat Team"
CONTACT_LABEL = "OneChat Contact Label"
AUTO_REPLY = "OneChat Auto Reply"
FORM = "WhatsApp Flow"
SCOPED = {f"tab{name}" for name in (MESSAGE, CONTACT, CONVERSATION, SESSION)}

PERIODS = {"24": 24, "168": 168, "720": 720, "2160": 2160}
HOURLY_UP_TO = 48
TOP = 10
AUTOMATED = ("Bot", "Auto reply", "Away message")
BANDS = (
	(300, "Under 5 min"),
	(900, "5–15 min"),
	(3600, "15–60 min"),
	(14400, "1–4 hours"),
	(86400, "4–24 hours"),
	(None, "Over a day"),
)
DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
REF = re.compile(r"\[ref:([A-Za-z0-9]{4,12})\]")


REPORT_TTL = 300


@frappe.whitelist()
def report(
	tab: str = "overview",
	period: int | str = "168",
	start: int | str | None = None,
	end: str | None = None,
	fresh: bool | int | str = 0,
):
	require_admin()
	from onechat.workspace.session import require_read

	require_read("OneChat Message")
	builder = TABS.get(tab)
	if not builder:
		frappe.throw(_("Unknown insights tab."))

	key = "onechat:insights:" + frappe.generate_hash(
		json.dumps([frappe.session.user, tab, period, start, end, numbers.hidden()], default=str), length=20
	)
	if not cint(fresh):
		cached = frappe.cache().get_value(key)
		if cached:
			return cached

	span = window(period, start, end)
	result = {
		**builder(span),
		"range": {"since": str(span.since), "until": str(span.until), "hourly": span.hourly},
		"generated_at": str(now_datetime()),
	}
	frappe.cache().set_value(key, result, expires_in_sec=REPORT_TTL)
	return result


def window(period, start=None, end=None):
	if period == "custom":
		if not (start and end):
			frappe.throw(_("Pick a start and end date."))
		since, until = get_datetime(start), get_datetime(end)
		if since > until:
			since, until = until, since
	else:
		until = now_datetime()
		since = until - timedelta(hours=PERIODS.get(str(period), 168))

	length = until - since
	return frappe._dict(
		since=since, until=until, previous=since - length, hourly=length <= timedelta(hours=HOURLY_UP_TO)
	)


def slot(value, hourly):
	return value.strftime("%Y-%m-%d %H:00" if hourly else "%Y-%m-%d")


def slots(span):
	if span.hourly:
		cursor, step = span.since.replace(minute=0, second=0, microsecond=0), timedelta(hours=1)
	else:
		cursor, step = datetime.combine(span.since.date(), time()), timedelta(days=1)

	out = []
	while cursor <= span.until:
		out.append(slot(cursor, span.hourly))
		cursor += step
	return out


def between(field, since, until):
	return (field >= since) & (field <= until)


def scoped(field, condition):
	if field.table and field.table.get_table_name() in SCOPED:
		shown = numbers.condition(field.table)
		if shown is not None:
			return condition & shown
	return condition


def inside(field, span):
	return scoped(field, between(field, span.since, span.until))


def before(field, span):
	return scoped(field, between(field, span.previous, span.since))


def count(table, condition):
	return cint(frappe.qb.from_(table).select(Count("*")).where(condition).run()[0][0])


def average(table, column, condition):
	value = frappe.qb.from_(table).select(Avg(column)).where(condition).run()[0][0]
	return round(flt(value)) if value is not None else None


def grouped(table, column, condition, value=None):
	query = (
		frappe.qb.from_(table)
		.select(column.as_("key"), (value or Count("*")).as_("value"))
		.where(condition)
		.groupby(column)
	)
	return {row.key: row.value for row in query.run(as_dict=True)}


def ranked(values, limit=TOP, blank="Other"):
	rows = [{"name": key or blank, "value": cint(value)} for key, value in values.items() if value]
	return sorted(rows, key=lambda row: row["value"], reverse=True)[:limit]


def timeline(table, field, span, condition=None, split=None):
	day = Date(field)
	columns, groups = [day.as_("day")], [day]
	if span.hourly:
		hour = Extract(DatePart.hour, field)
		columns.append(hour.as_("hour"))
		groups.append(hour)
	if split is not None:
		columns.append(split.as_("split"))
		groups.append(split)

	query = frappe.qb.from_(table).select(*columns, Count("*").as_("count")).where(inside(field, span))
	if condition is not None:
		query = query.where(condition)

	out = defaultdict(Counter)
	for row in query.groupby(*groups).run(as_dict=True):
		at = datetime.combine(getdate(row.day), time(cint(row.get("hour")) if span.hourly else 0))
		out[slot(at, span.hourly)][row.get("split") if split is not None else "count"] += cint(row.count)
	return out


def plot(span, **columns):
	return [{"at": at, **{name: pick(at) for name, pick in columns.items()}} for at in slots(span)]


def picker(data, *keys):
	return lambda at: sum(data.get(at, Counter()).get(key, 0) for key in (keys or ("count",)))


def status_counts(condition):
	message = frappe.qb.DocType(MESSAGE)
	status = Lower(IfNull(message.status, ""))
	return Counter(grouped(message, status, condition))


def delivery(counts):
	sent = sum(counts.values())
	delivered = counts.get("delivered", 0) + counts.get("read", 0)
	read = counts.get("read", 0)
	return {
		"sent": sent,
		"delivered": delivered,
		"read": read,
		"failed": counts.get("failed", 0),
		"delivery_rate": percent(delivered, sent),
		"read_rate": percent(read, delivered),
	}


def percent(part, whole):
	return round(part * 100 / whole, 1) if whole else None


def label_of(doctype, names, field):
	names = [name for name in names if name]
	if not names:
		return {}
	return {
		row.name: row.get(field) or row.name
		for row in frappe.get_all(doctype, filters={"name": ["in", names]}, fields=["name", field])
	}


def outgoing(message):
	return (message.type == "Outgoing") & (IfNull(message.content_type, "") != "reaction")


def totals(since, until):
	message = frappe.qb.DocType(MESSAGE)
	conversation = frappe.qb.DocType(CONVERSATION)
	contact = frappe.qb.DocType(CONTACT)
	sent = between(message.creation, since, until) & outgoing(message)
	return {
		"received": count(message, between(message.creation, since, until) & (message.type == "Incoming")),
		"sent": count(message, sent),
		"conversations": count(conversation, between(conversation.opened_at, since, until)),
		"resolved": count(conversation, between(conversation.resolved_at, since, until)),
		"response": average(
			conversation, conversation.response_seconds, between(conversation.first_response_at, since, until)
		),
		"contacts": count(contact, between(contact.creation, since, until)),
		"opt_outs": count(contact, between(contact.opted_out_at, since, until)),
		"read_rate": delivery(status_counts(sent))["read_rate"],
		**satisfaction(conversation, between(conversation.csat_at, since, until)),
	}


def satisfaction(conversation, condition):
	rated = count(
		conversation, condition & conversation.csat_score.isnotnull() & (conversation.csat_score > 0)
	)
	great = count(conversation, condition & (conversation.csat_score == 3))
	return {"ratings": rated, "satisfaction": percent(great, rated)}


def overview(span):
	message = frappe.qb.DocType(MESSAGE)
	sent = inside(message.creation, span) & outgoing(message)
	traffic = timeline(message, message.creation, span, split=message.type)
	sources = grouped(message, IfNull(message.source, ""), sent)
	return {
		"now": totals(span.since, span.until),
		"before": totals(span.previous, span.since),
		"traffic": plot(span, received=picker(traffic, "Incoming"), sent=picker(traffic, "Outgoing")),
		"sources": ranked(sources),
		"delivery": delivery(status_counts(sent)),
	}


def bands(values):
	counts = Counter()
	for value in values:
		for limit, label in BANDS:
			if limit is None or cint(value) < limit:
				counts[label] += 1
				break
	return [{"name": label, "value": counts.get(label, 0)} for limit, label in BANDS]


def heatmap(span):
	message = frappe.qb.DocType(MESSAGE)
	day, hour = Date(message.creation), Extract(DatePart.hour, message.creation)
	cells = Counter()
	for row in (
		frappe.qb.from_(message)
		.select(day.as_("day"), hour.as_("hour"), Count("*").as_("count"))
		.where(inside(message.creation, span) & (message.type == "Incoming"))
		.groupby(day, hour)
		.run(as_dict=True)
	):
		cells[(getdate(row.day).weekday(), cint(row.hour))] += cint(row.count)

	return [
		{"day": DAYS[weekday], "hour": f"{hour:02d}", "count": cells.get((weekday, hour), 0)}
		for weekday in range(7)
		for hour in range(24)
	]


def backlog():
	contact = frappe.qb.DocType(CONTACT)
	is_open = contact.conversation_status == "Open"
	return {
		"open": count(contact, is_open),
		"pending": count(contact, contact.conversation_status == "Pending"),
		"unassigned": count(contact, is_open & (IfNull(contact.assigned_to, "") == "")),
		"waiting": count(contact, is_open & (contact.last_message_type == "Incoming")),
	}


def conversations(span):
	conversation = frappe.qb.DocType(CONVERSATION)
	message = frappe.qb.DocType(MESSAGE)
	label = frappe.qb.DocType(CONTACT_LABEL)
	opened_in = inside(conversation.opened_at, span)
	opened = timeline(conversation, conversation.opened_at, span)
	resolved = timeline(conversation, conversation.resolved_at, span)
	channel = IfNull(conversation.channel, "WhatsApp")
	waits = seconds_by(
		conversation, channel, conversation.first_response_at, conversation.response_seconds, span
	)
	fixes = seconds_by(conversation, channel, conversation.resolved_at, conversation.resolution_seconds, span)
	responses = [value for values in waits.values() for value in values]
	resolutions = [value for values in fixes.values() for value in values]
	unanswered = grouped(conversation, channel, opened_in & conversation.first_response_at.isnull())
	labels = (
		frappe.qb.from_(conversation)
		.join(label)
		.on(
			(label.parent == conversation.contact)
			& (label.parenttype == CONTACT)
			& (label.parentfield == "labels")
		)
		.select(label.label.as_("key"), Count("*").as_("value"))
		.where(opened_in)
		.groupby(label.label)
		.run(as_dict=True)
	)
	accounts = grouped(conversation, IfNull(conversation.whatsapp_account, ""), opened_in)
	channels = grouped(conversation, channel, opened_in)
	return {
		"summary": {
			"opened": sum(sum(value.values()) for value in opened.values()),
			"resolved": len(resolutions),
			"response": mean_of(responses),
			"median_response": median_of(responses),
			"resolution": mean_of(resolutions),
			"unanswered": sum(unanswered.values()),
			"bot_only": count(
				conversation,
				opened_in & conversation.bot_flow.isnotnull() & (IfNull(conversation.agent_replies, 0) == 0),
			),
		},
		"backlog": backlog(),
		"flow": plot(span, opened=picker(opened), resolved=picker(resolved)),
		"response_bands": bands([value for value in responses if value is not None]),
		"heatmap": heatmap(span),
		"content_types": ranked(
			grouped(
				message,
				IfNull(message.content_type, ""),
				inside(message.creation, span) & (message.type == "Incoming"),
			),
			blank="text",
		),
		"labels": ranked({row.key: row.value for row in labels}),
		"accounts": ranked(accounts, blank="Unknown") if len(accounts) > 1 else [],
		"channels": ranked(channels) if len(channels) > 1 else [],
		"by_channel": by_channel(channels, waits, fixes, unanswered) if len(channels) > 1 else [],
		"comments": comment_counts(span),
	}


def seconds_by(table, channel, at, seconds, span):
	out = defaultdict(list)
	for row in (
		frappe.qb.from_(table)
		.select(channel.as_("channel"), seconds.as_("seconds"))
		.where(inside(at, span))
		.run(as_dict=True)
	):
		out[row.channel].append(row.seconds)
	return out


def mean_of(values):
	values = [value for value in values if value is not None]
	return round(sum(values) / len(values)) if values else None


def median_of(values):
	values = [value for value in values if value is not None]
	return round(median(values)) if values else None


def by_channel(opened, waits, fixes, unanswered):
	return [
		{
			"channel": name,
			"opened": cint(opened.get(name)),
			"resolved": len(fixes.get(name, [])),
			"resolution_rate": percent(len(fixes.get(name, [])), cint(opened.get(name))),
			"response": mean_of(waits.get(name, [])),
			"median_response": median_of(waits.get(name, [])),
			"resolution": mean_of(fixes.get(name, [])),
			"unanswered": cint(unanswered.get(name)),
		}
		for name in sorted(set(opened) | set(waits) | set(fixes))
	]


def per_user(table, column, condition, value=None):
	query = frappe.qb.from_(table).select(column.as_("user"), Count("*").as_("count"))
	if value is not None:
		query = query.select(Avg(value).as_("average"))
	return {
		row.user: row for row in query.where(condition & column.isnotnull()).groupby(column).run(as_dict=True)
	}


def team(span):
	conversation = frappe.qb.DocType(CONVERSATION)
	message = frappe.qb.DocType(MESSAGE)
	contact = frappe.qb.DocType(CONTACT)
	assigned = per_user(conversation, conversation.assigned_to, inside(conversation.opened_at, span))
	replies = per_user(message, message.owner, inside(message.creation, span) & (message.source == "Agent"))
	first = per_user(
		conversation,
		conversation.first_response_by,
		inside(conversation.first_response_at, span),
		conversation.response_seconds,
	)
	resolved = per_user(
		conversation,
		conversation.resolved_by,
		inside(conversation.resolved_at, span),
		conversation.resolution_seconds,
	)
	rated = per_user(
		conversation,
		conversation.resolved_by,
		inside(conversation.csat_at, span) & (conversation.csat_score > 0),
		conversation.csat_score,
	)
	open_now = per_user(contact, contact.assigned_to, contact.conversation_status == "Open")

	agents = {
		row.user: row
		for row in frappe.get_all(
			AGENT, filters={"enabled": 1}, fields=["user", "full_name", "availability", "profile_image"]
		)
	}
	people = set(agents) | set(assigned) | set(replies) | set(first) | set(resolved)
	people -= {"Guest", "Administrator"} - set(agents)

	def metric(source, user, field="count"):
		row = source.get(user)
		return (
			(round(flt(row.get(field))) if row.get(field) is not None else None)
			if row
			else (0 if field == "count" else None)
		)

	rows = []
	for user in people:
		agent = agents.get(user) or frappe._dict()
		rows.append(
			{
				"user": user,
				"name": agent.full_name or get_fullname(user),
				"image": agent.profile_image,
				"availability": agent.availability if agent else None,
				"assigned": metric(assigned, user),
				"replies": metric(replies, user),
				"first_responses": metric(first, user),
				"response": metric(first, user, "average"),
				"resolved": metric(resolved, user),
				"resolution": metric(resolved, user, "average"),
				"rating": round(flt(rated[user].average), 1) if user in rated else None,
				"ratings": metric(rated, user),
				"open": metric(open_now, user),
			}
		)
	rows.sort(key=lambda row: (row["replies"], row["resolved"]), reverse=True)

	teams = (
		frappe.qb.from_(conversation)
		.select(
			conversation.team.as_("team"),
			Count("*").as_("opened"),
			Avg(conversation.response_seconds).as_("response"),
		)
		.where(inside(conversation.opened_at, span) & conversation.team.isnotnull())
		.groupby(conversation.team)
		.run(as_dict=True)
	)
	team_resolved = grouped(
		conversation,
		conversation.team,
		inside(conversation.resolved_at, span) & conversation.team.isnotnull(),
	)
	names = label_of(TEAM, [row.team for row in teams], "team_name")
	agent_replies = timeline(message, message.creation, span, message.source == "Agent")

	return {
		"agents": rows,
		"teams": [
			{
				"team": names.get(row.team, row.team),
				"opened": cint(row.opened),
				"resolved": cint(team_resolved.get(row.team)),
				"response": round(flt(row.response)) if row.response is not None else None,
			}
			for row in sorted(teams, key=lambda row: row.opened, reverse=True)
		],
		"availability": dict(Counter(agent.availability or "Available" for agent in agents.values())),
		"replies": plot(span, replies=picker(agent_replies)),
	}


def node_labels(flows):
	out = {}
	for name, graph in (
		frappe.get_all(
			FLOW, filters={"name": ["in", list(flows)]}, fields=["name", "graph_json"], as_list=True
		)
		if flows
		else []
	):
		try:
			nodes = json.loads(graph or "{}").get("nodes") or []
		except ValueError:
			nodes = []
		out[name] = {node.get("id"): (node.get("data") or {}).get("label") for node in nodes}
	return out


def automation(span):
	session = frappe.qb.DocType(SESSION)
	message = frappe.qb.DocType(MESSAGE)
	conversation = frappe.qb.DocType(CONVERSATION)
	run_log = frappe.qb.DocType(RUN_LOG)
	started_in = inside(session.creation, span)

	per_flow = defaultdict(Counter)
	for row in (
		frappe.qb.from_(session)
		.select(session.flow, session.status, Count("*").as_("count"))
		.where(started_in)
		.groupby(session.flow, session.status)
		.run(as_dict=True)
	):
		per_flow[row.flow][row.status] += cint(row.count)

	drops = (
		frappe.qb.from_(session)
		.select(session.flow, session.current_node, session.status, Count("*").as_("count"))
		.where(
			started_in
			& session.status.isin(["Expired", "Stopped", "Failed"])
			& session.current_node.isnotnull()
		)
		.groupby(session.flow, session.current_node, session.status)
		.orderby(Count("*"), order=Order.desc)
		.limit(TOP)
		.run(as_dict=True)
	)
	flow_names = label_of(FLOW, list(per_flow) + [row.flow for row in drops], "flow_name")
	steps = node_labels({row.flow for row in drops})

	outcomes = Counter()
	flows = []
	for flow, statuses in per_flow.items():
		outcomes.update(statuses)
		started = sum(statuses.values())
		flows.append(
			{
				"flow": flow,
				"name": flow_names.get(flow, flow),
				"started": started,
				"completed": statuses.get("Completed", 0),
				"active": statuses.get("Running", 0) + statuses.get("Waiting", 0),
				"stopped": statuses.get("Stopped", 0),
				"expired": statuses.get("Expired", 0),
				"failed": statuses.get("Failed", 0),
				"completion_rate": percent(statuses.get("Completed", 0), started),
			}
		)
	flows.sort(key=lambda row: row["started"], reverse=True)

	opened_in = inside(conversation.opened_at, span)
	with_bot = opened_in & conversation.bot_flow.isnotnull()
	replies = timeline(
		message, message.creation, span, message.source.isin(["Agent", *AUTOMATED]), split=message.source
	)
	started = timeline(session, session.creation, span)
	failures = grouped(
		run_log,
		IfNull(run_log.error_message, ""),
		inside(run_log.creation, span) & (run_log.status == "Failed"),
	)

	return {
		"summary": {
			"started": sum(outcomes.values()),
			"completed": outcomes.get("Completed", 0),
			"expired": outcomes.get("Expired", 0),
			"failed": outcomes.get("Failed", 0),
			"conversations": count(conversation, opened_in),
			"with_bot": count(conversation, with_bot),
			"bot_only": count(conversation, with_bot & (IfNull(conversation.agent_replies, 0) == 0)),
			"automated": count(message, inside(message.creation, span) & message.source.isin(AUTOMATED)),
			"auto_replies": count(message, inside(message.creation, span) & (message.source == "Auto reply")),
			"notifications": count(
				message, inside(message.creation, span) & (message.source == "Notification")
			),
		},
		"outcomes": ranked(outcomes),
		"flows": flows[:TOP],
		"drop_offs": [
			{
				"flow": flow_names.get(row.flow, row.flow),
				"step": steps.get(row.flow, {}).get(row.current_node) or row.current_node,
				"status": row.status,
				"count": cint(row.count),
			}
			for row in drops
		],
		"activity": plot(
			span,
			started=picker(started),
			agent=picker(replies, "Agent"),
			automated=picker(replies, *AUTOMATED),
		),
		"auto_reply_rules": frappe.get_all(
			AUTO_REPLY,
			fields=["name", "rule_name", "enabled", "reply_count", "last_replied_at"],
			order_by="reply_count desc",
			limit=TOP,
		),
		"failures": [
			{"name": last_line(row["name"]), "value": row["value"]}
			for row in ranked(failures, limit=5, blank="")
		],
	}


def last_line(text):
	lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
	return lines[-1][:160] if lines else ""


def chat_links(span):
	message = frappe.qb.DocType(MESSAGE)
	texts = (
		frappe.qb.from_(message)
		.select(message.message)
		.where(
			inside(message.creation, span) & (message.type == "Incoming") & message.message.like("%[ref:%")
		)
		.run(pluck=True)
	)
	codes = Counter(match.group(1).upper() for text in texts for match in [REF.search(text or "")] if match)
	if not codes:
		return []

	titles = {
		row.ref_code: row.title
		for row in frappe.get_all(
			"OneChat Chat Link", filters={"ref_code": ["in", list(codes)]}, fields=["ref_code", "title"]
		)
	}
	return ranked({titles.get(code) or code: value for code, value in codes.items()})


def campaigns(span):
	message = frappe.qb.DocType(MESSAGE)
	contact = frappe.qb.DocType(CONTACT)
	template = frappe.qb.DocType(TEMPLATE)
	in_range = inside(message.creation, span)
	templated = (
		in_range & (message.type == "Outgoing") & message.template.isnotnull() & (message.template != "")
	)

	per_template = defaultdict(Counter)
	status = Lower(IfNull(message.status, ""))
	for row in (
		frappe.qb.from_(message)
		.select(message.template, status.as_("status"), Count("*").as_("count"))
		.where(templated)
		.groupby(message.template, status)
		.run(as_dict=True)
	):
		per_template[row.template][row.status] += cint(row.count)

	names = label_of(TEMPLATE, list(per_template), "template_name")
	templates = sorted(
		(
			{"template": key, "name": names.get(key, key), **delivery(counts)}
			for key, counts in per_template.items()
		),
		key=lambda row: row["sent"],
		reverse=True,
	)[:TOP]

	broadcast_filters = {"creation": ["between", [span.since, span.until]], "docstatus": ["<", 2]}
	if numbers.hidden():
		broadcast_filters["whatsapp_account"] = ["not in", numbers.hidden()]
	broadcasts = frappe.get_all(
		BROADCAST,
		filters=broadcast_filters,
		fields=["name", "title", "status", "recipient_count", "sent_count", "skipped_count", "creation"],
		order_by="creation desc",
		limit=TOP,
	)
	if broadcasts:
		reach = defaultdict(Counter)
		for row in (
			frappe.qb.from_(message)
			.select(
				message.bulk_message_reference.as_("broadcast"), status.as_("status"), Count("*").as_("count")
			)
			.where(message.bulk_message_reference.isin([row.name for row in broadcasts]))
			.groupby(message.bulk_message_reference, status)
			.run(as_dict=True)
		):
			reach[row.broadcast][row.status] += cint(row.count)
		for row in broadcasts:
			row.update(delivery(reach.get(row.name, Counter())))

	joined = timeline(contact, contact.creation, span)
	left = timeline(contact, contact.opted_out_at, span)
	forms = grouped(
		message,
		message.flow,
		in_range & (message.type == "Incoming") & (message.content_type == "flow") & message.flow.isnotnull(),
	)
	form_names = label_of(FORM, list(forms), "flow_name")
	failures = grouped(
		message,
		IfNull(message.error_message, ""),
		in_range & (message.type == "Outgoing") & (Lower(IfNull(message.status, "")) == "failed"),
	)

	return {
		"funnel": delivery(status_counts(templated)),
		"templates": templates,
		"failures": ranked(failures, limit=8, blank=""),
		"broadcasts": broadcasts,
		"audience": plot(span, joined=picker(joined), opted_out=picker(left)),
		"audience_summary": {
			"joined": count(contact, inside(contact.creation, span)),
			"opted_out": count(contact, inside(contact.opted_out_at, span)),
			"opted_out_total": count(contact, contact.opted_out == 1),
			"contacts": count(contact, contact.name.isnotnull()),
		},
		"chat_links": chat_links(span),
		"forms": ranked({form_names.get(key, key): value for key, value in forms.items()}),
		"template_status": ranked(
			grouped(template, IfNull(template.status, ""), template.name.isnotnull()), blank="Pending"
		),
	}


def orders(span):
	from onechat.insights.orders import report as build

	return build(span)


def costs(span):
	from onechat.insights.costs import costs as build

	return build(span)


TABS = {
	"costs": costs,
	"overview": overview,
	"conversations": conversations,
	"team": team,
	"automation": automation,
	"campaigns": campaigns,
	"orders": orders,
}


def comment_counts(span):
	message = frappe.qb.DocType(MESSAGE)
	comment = message.content_type == "comment"
	row = (
		frappe.qb.from_(message)
		.select(
			Sum(Case().when(comment, 1).else_(0)).as_("received"),
			Sum(Case().when(comment & (message.comment_replied == 1), 1).else_(0)).as_("replied"),
			Sum(Case().when(message.content_type == "comment_reply", 1).else_(0)).as_("public"),
			Sum(Case().when(comment & (message.comment_hidden == 1), 1).else_(0)).as_("hidden"),
		)
		.where(inside(message.creation, span) & message.content_type.isin(["comment", "comment_reply"]))
		.run(as_dict=True)[0]
	)
	if not cint(row.received):
		return None
	return {key: cint(value) for key, value in row.items()}
