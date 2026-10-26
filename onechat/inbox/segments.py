import frappe
from frappe import _
from frappe.query_builder import Order
from frappe.query_builder.functions import Count, IfNull
from frappe.utils import add_days, cint, flt, get_datetime, now_datetime, nowdate

from onechat import integrations
from onechat.api_types import JSON
from onechat.inbox import visibility
from onechat.inbox.conversations import CONTACT, CONTACT_LABEL, LABEL, guard
from onechat.inbox.scores import GROUPS
from onechat.inbox.visibility import check as check_visible
from onechat.integrations import documents, links
from onechat.workspace import numbers
from onechat.workspace.session import require, require_admin

SEGMENT = "OneChat Segment"
TEAM = "OneChat Team"
SAMPLE = 8
OVERVIEW_CACHE = "onechat:segments:overview:"
OVERVIEW_TTL = 120
MATCHES = ("all", "any")
NUMBER_OPS = ("gt", "gte", "lt", "lte", "eq", "between")
DATE_OPS = ("within", "over", "never")
CHOICE_OPS = ("in", "not_in")
TEXT_OPS = ("is", "contains", "set", "not_set")
FLAG_OPS = ("yes", "no")
LABEL_OPS = ("has_any", "has_none")
FIELDS = {
	"value_group": {"label": "Value group", "type": "choice", "group": "Scores"},
	"engagement_score": {"label": "Engagement score", "type": "number", "group": "Scores"},
	"favourite_category": {"label": "Favourite category", "type": "text", "group": "Scores"},
	"lifetime_value": {"label": "Lifetime value", "type": "number", "group": "Purchases"},
	"order_count": {"label": "Purchases", "type": "number", "group": "Purchases"},
	"outstanding_amount": {"label": "Outstanding", "type": "number", "group": "Purchases"},
	"last_purchase_on": {"label": "Last purchase", "type": "date", "group": "Purchases"},
	"first_purchase_on": {"label": "First purchase", "type": "date", "group": "Purchases"},
	"last_reply_at": {"label": "Last reply from them", "type": "date", "group": "Activity"},
	"last_message_at": {"label": "Last message", "type": "date", "group": "Activity"},
	"creation": {"label": "Contact added", "type": "date", "group": "Activity"},
	"labels": {"label": "Labels", "type": "labels", "group": "Contact"},
	"team": {"label": "Team", "type": "choice", "group": "Contact"},
	"assigned_to": {"label": "Assigned to", "type": "choice", "group": "Contact"},
	"conversation_status": {"label": "Chat status", "type": "choice", "group": "Contact"},
	"reference_doctype": {"label": "Linked record", "type": "choice", "group": "Contact"},
	"opted_out": {"label": "Opted out of marketing", "type": "flag", "group": "Contact"},
}
PURCHASE_FIELDS = (
	"value_group",
	"favourite_category",
	"lifetime_value",
	"order_count",
	"outstanding_amount",
	"last_purchase_on",
	"first_purchase_on",
)
OPS = {
	"number": NUMBER_OPS,
	"date": DATE_OPS,
	"choice": CHOICE_OPS,
	"text": TEXT_OPS,
	"flag": FLAG_OPS,
	"labels": LABEL_OPS,
}


def choices(field):
	if field == "value_group":
		return [{"value": key, "label": _(key), "hint": _(meta["hint"])} for key, meta in GROUPS.items()]
	if field == "conversation_status":
		return [{"value": key, "label": _(key)} for key in ("Open", "Pending", "Resolved")]
	if field == "team":
		return [
			{"value": name, "label": name} for name in frappe.get_all(TEAM, pluck="name", order_by="name asc")
		]
	if field == "labels":
		return [
			{"value": row.name, "label": row.get("label_name") or row.name, "color": row.get("color")}
			for row in frappe.get_all(LABEL, fields=["*"], order_by="name asc")
		]
	if field == "assigned_to":
		users = frappe.get_all(
			CONTACT, filters={"assigned_to": ["is", "set"]}, pluck="assigned_to", distinct=True
		)
		return [{"value": user, "label": frappe.utils.get_fullname(user)} for user in sorted(set(users))]
	if field == "reference_doctype":
		names = frappe.get_all(
			CONTACT, filters={"reference_doctype": ["is", "set"]}, pluck="reference_doctype", distinct=True
		)
		names += frappe.get_all(
			links.LINK, filters={"parenttype": CONTACT}, pluck="link_doctype", distinct=True
		)
		return [{"value": name, "label": _(name)} for name in sorted(set(names))]
	return []


def available():
	return frappe.get_meta(CONTACT).has_field("value_group")


@frappe.whitelist()
def fields():
	guard()
	meta = frappe.get_meta(CONTACT)
	commerce = integrations.has_purchases()
	out = []
	for key, spec in catalog().items():
		if not spec.get("document"):
			if key not in ("labels", "creation") and not meta.has_field(key):
				continue
			if key in PURCHASE_FIELDS and not commerce:
				continue
		row = {
			"key": key,
			**spec,
			"label": _(spec["label"]),
			"group": _(spec["group"]),
			"ops": OPS[spec["type"]],
		}
		if spec["type"] in ("choice", "labels") and not spec.get("document"):
			row["options"] = choices(key)
		out.append(row)
	return out


def catalog():
	return {**FIELDS, **documents.catalog()}


def parse_rules(rules):
	rules = frappe.parse_json(rules) if isinstance(rules, str) else rules
	known = catalog()
	return [
		rule
		for rule in rules or []
		if isinstance(rule, dict) and rule.get("field") in known and rule.get("op")
	]


def as_list(value):
	if isinstance(value, str):
		value = frappe.parse_json(value) if value.startswith("[") else [value]
	return [item for item in value or [] if item not in (None, "")]


def between(value):
	low, high = ([*list(value), None, None])[:2] if isinstance(value, list | tuple) else (None, None)
	if low in (None, "") or high in (None, ""):
		return None, None
	return flt(low), flt(high)


def date_edge(value, date_only):
	days = cint(value)
	if days <= 0:
		return None
	return add_days(nowdate() if date_only else now_datetime(), -days)


def column_criterion(column, kind, op, value, date_only=False):
	if kind == "flag":
		return column == (1 if op == "yes" else 0)

	if kind == "choice":
		names = as_list(value)
		if not names:
			return None
		return column.isin(names) if op == "in" else (column.notin(names) | column.isnull())

	if kind == "text":
		if op == "set":
			return column.isnotnull() & (column != "")
		if op == "not_set":
			return column.isnull() | (column == "")
		if not value:
			return None
		return column.like(f"%{value}%") if op == "contains" else (column == value)

	if kind == "number":
		if op == "between":
			low, high = between(value)
			if low is None:
				return None
			return column.between(low, high)
		if value in (None, ""):
			return None
		number = flt(value)
		return {
			"gt": column > number,
			"gte": column >= number,
			"lt": column < number,
			"lte": column <= number,
			"eq": column == number,
		}[op]

	if kind == "date":
		if op == "never":
			return column.isnull()
		edge = date_edge(value, date_only)
		if edge is None:
			return None
		return column >= edge if op == "within" else (column < edge)

	return None


def filter_criterion(fieldname, kind, op, value, date_only=False):
	if kind == "flag":
		return [[fieldname, "=", 1 if op == "yes" else 0]]

	if kind == "choice":
		names = as_list(value)
		if not names:
			return None
		return [[fieldname, "in" if op == "in" else "not in", names]]

	if kind == "text":
		if op == "set":
			return [[fieldname, "is", "set"]]
		if op == "not_set":
			return [[fieldname, "is", "not set"]]
		if not value:
			return None
		return [[fieldname, "like", f"%{value}%"]] if op == "contains" else [[fieldname, "=", value]]

	if kind == "number":
		if op == "between":
			low, high = between(value)
			return [[fieldname, "between", [low, high]]] if low is not None else None
		if value in (None, ""):
			return None
		return [[fieldname, {"gt": ">", "gte": ">=", "lt": "<", "lte": "<=", "eq": "="}[op], flt(value)]]

	if kind == "date":
		if op == "never":
			return [[fieldname, "is", "not set"]]
		edge = date_edge(value, date_only)
		if edge is None:
			return None
		return [[fieldname, ">=" if op == "within" else "<", str(edge)]]

	return None


def document_criterion(contact, spec, op, value):
	kind, fieldname, date_only = spec["type"], spec["fieldname"], spec.get("date_only", False)
	# "is none of" means no such document at all, so it is the "is any of" match turned inside out.
	anti = kind == "choice" and op == "not_in"
	inner = "in" if anti else op
	filters = filter_criterion(fieldname, kind, inner, value, date_only)
	if filters is None:
		return None

	link = frappe.qb.DocType(links.LINK)
	ref = frappe.qb.DocType(CONTACT).as_("ref")
	matched = []
	for party_type in documents.SOURCES[spec["document"]]["parties"]:
		names = documents.parties_with(
			spec["document"],
			party_type,
			lambda table: column_criterion(table[fieldname], kind, inner, value, date_only),
			filters,
		)
		if isinstance(names, list) and not names:
			continue
		matched.append(
			frappe.qb.from_(ref)
			.select(ref.name)
			.where((ref.reference_doctype == party_type) & ref.reference_docname.isin(names))
		)
		matched.append(
			frappe.qb.from_(link)
			.select(link.parent)
			.where(
				(link.parenttype == CONTACT) & (link.link_doctype == party_type) & link.link_name.isin(names)
			)
		)

	if not matched:
		return contact.name.isnotnull() if anti else contact.name.isnull()

	parts = [contact.name.notin(sub) if anti else contact.name.isin(sub) for sub in matched]
	joined = parts[0]
	for part in parts[1:]:
		joined = (joined & part) if anti else (joined | part)
	return joined


def criterion(contact, rule):
	field, op, value = rule["field"], rule["op"], rule.get("value")
	spec = catalog()[field]
	if spec.get("document"):
		return document_criterion(contact, spec, op, value)
	kind = spec["type"]
	column = contact[field]

	if kind == "labels":
		names = as_list(value)
		if not names:
			return None
		link = frappe.qb.DocType(CONTACT_LABEL)
		tagged = (
			frappe.qb.from_(link)
			.select(link.parent)
			.where((link.parenttype == CONTACT) & (link.parentfield == "labels") & link.label.isin(names))
		)
		return contact.name.isin(tagged) if op == "has_any" else contact.name.notin(tagged)

	if field == "reference_doctype":
		names = as_list(value)
		if not names:
			return None
		table = frappe.qb.DocType(links.LINK)
		sub = (
			frappe.qb.from_(table)
			.select(table.parent)
			.where((table.parenttype == CONTACT) & table.link_doctype.isin(names))
		)
		if op == "in":
			return column.isin(names) | contact.name.isin(sub)
		return (column.notin(names) | column.isnull()) & contact.name.notin(sub)

	return column_criterion(column, kind, op, value, field.endswith("_on"))


def build(rules, match="all"):
	contact = frappe.qb.DocType(CONTACT)
	parts = [part for part in (criterion(contact, rule) for rule in parse_rules(rules)) if part is not None]
	condition = contact.disable == 0
	scope = visibility.shown(contact)
	if scope is not None:
		condition = condition & scope
	if parts:
		joined = parts[0]
		for part in parts[1:]:
			joined = (joined | part) if match == "any" else (joined & part)
		condition = condition & joined
	return contact, condition


def count(rules, match="all"):
	contact, condition = build(rules, match)
	return cint(frappe.qb.from_(contact).select(Count("*")).where(condition).run()[0][0])


def member_query(rules, match="all"):
	contact, condition = build(rules, match)
	return frappe.qb.from_(contact).where(condition), contact


MEMBER_FIELDS = (
	"name",
	"contact_name",
	"wa_number",
	"mobile_no",
	"email",
	"opted_out",
	"value_group",
	"favourite_category",
	"lifetime_value",
	"engagement_score",
)


def members(name, fields=MEMBER_FIELDS):
	segment = frappe.get_doc(SEGMENT, name)
	query, contact = member_query(segment.rules, segment.match)
	return query.select(*[contact[field] for field in fields]).orderby(contact.name).run(as_dict=True)


def check_match(match):
	if match not in MATCHES:
		frappe.throw(_("Choose whether contacts must match all rules or any rule."))
	return match


@frappe.whitelist()
def preview(rules: JSON, match: str = "all"):
	guard()
	if not available():
		frappe.throw(_("Run bench migrate to finish setting up segments."))
	check_match(match)
	query, contact = member_query(rules, match)
	sample = (
		query.select(
			contact.name,
			contact.contact_name,
			contact.mobile_no,
			contact.profile_image,
			contact.value_group,
			contact.engagement_score,
			contact.opted_out,
		)
		.orderby(contact.engagement_score, order=Order.desc)
		.limit(SAMPLE)
		.run(as_dict=True)
	)
	total = count(rules, match)
	reachable = (
		count([*parse_rules(rules), {"field": "opted_out", "op": "no"}], match) if match == "all" else None
	)
	return {"count": total, "reachable": reachable, "sample": sample}


def refresh_count(name):
	segment = frappe.get_doc(SEGMENT, name)
	total = count(segment.rules, segment.match)
	frappe.db.set_value(
		SEGMENT, name, {"member_count": total, "counted_at": now_datetime()}, update_modified=False
	)
	return total


@frappe.whitelist()
def segments():
	guard()
	rows = frappe.get_all(
		SEGMENT,
		fields=[
			"name",
			"segment_name",
			"description",
			"match",
			"rules",
			"member_count",
			"counted_at",
			"modified",
			"owner",
		],
		order_by="segment_name asc",
	)
	for row in rows:
		try:
			row.member_count = count(row.rules, row.match)
		except Exception:
			frappe.log_error(title=f"OneChat segment count: {row.name}")
		row.rules = parse_rules(row.rules)
		row.counted_at = str(get_datetime(row.counted_at)) if row.counted_at else None
		row.modified = str(row.modified)
	return rows


@frappe.whitelist()
def save_segment(
	segment_name: str,
	rules: JSON,
	match: str = "all",
	description: str | None = None,
	name: str | None = None,
):
	require_admin()
	require(SEGMENT, "write" if name else "create")
	check_match(match)
	segment_name = (segment_name or "").strip()
	if not segment_name:
		frappe.throw(_("Give the segment a name."))
	cleaned = parse_rules(rules)
	if not cleaned:
		frappe.throw(_("Add at least one rule."))
	values = {
		"segment_name": segment_name,
		"description": description,
		"match": match,
		"rules": frappe.as_json(cleaned),
	}
	if name:
		doc = frappe.get_doc(SEGMENT, name)
		doc.update(values)
		doc.save()
		if doc.name != segment_name:
			frappe.rename_doc(SEGMENT, doc.name, segment_name, force=True)
			doc = frappe.get_doc(SEGMENT, segment_name)
	else:
		doc = frappe.get_doc({"doctype": SEGMENT, **values}).insert()
	refresh_count(doc.name)
	return doc.name


@frappe.whitelist()
def delete_segment(name: str):
	require_admin()
	require(SEGMENT, "delete")
	used = frappe.get_all(
		"Bulk WhatsApp Message",
		filters={"segment": name, "status": ["in", ["Draft", "Queued", "In Progress"]]},
		pluck="name",
		limit=1,
	)
	if used:
		frappe.throw(_("Broadcast {0} is waiting to send to this segment. Cancel it first.").format(used[0]))
	frappe.delete_doc(SEGMENT, name)
	return True


@frappe.whitelist()
def contact_segments(contact: str):
	guard()
	check_visible(contact)
	if not available():
		return []
	out = []
	for row in frappe.get_all(
		SEGMENT, fields=["name", "segment_name", "rules", "match"], order_by="segment_name asc"
	):
		contact_table, condition = build(row.rules, row.match)
		found = (
			frappe.qb.from_(contact_table)
			.select(contact_table.name)
			.where(condition & (contact_table.name == contact))
			.limit(1)
			.run()
		)
		if found:
			out.append({"name": row.name, "segment_name": row.segment_name})
	return out


def recipients(name):
	return [
		{
			"mobile_number": row.wa_number or row.mobile_no,
			"recipient_name": row.contact_name,
			"recipient_data": frappe.as_json(
				{**{key: value for key, value in row.items() if value not in (None, "")}, "contact": row.name}
			),
		}
		for row in members(name)
		if (row.wa_number or row.mobile_no) and not row.opted_out
	]


ENGAGEMENT_BANDS = (("highly_engaged", 70, 100), ("engaged", 40, 69), ("quiet", 15, 39), ("inactive", 0, 14))


def engagement_counts(contact, base):
	score = IfNull(contact.engagement_score, 0)
	out = {}
	for key, low, high in ENGAGEMENT_BANDS:
		out[key] = cint(
			frappe.qb.from_(contact)
			.select(Count("*"))
			.where(base & (score >= low) & (score <= high))
			.run()[0][0]
		)
	return out


@frappe.whitelist()
def overview():
	guard()
	if not available():
		return {"groups": {}, "engagement": {}, "scored_at": None, "purchases": False}
	key = f"{OVERVIEW_CACHE}{frappe.session.user}:{','.join(numbers.hidden())}:{','.join(numbers.hidden_teams())}"
	cached = frappe.cache().get_value(key)
	if cached:
		return cached
	result = count_overview()
	frappe.cache().set_value(key, result, expires_in_sec=OVERVIEW_TTL)
	return result


def forget_overview():
	frappe.cache().delete_keys(OVERVIEW_CACHE)


def count_overview():
	contact = frappe.qb.DocType(CONTACT)
	base = contact.disable == 0
	scope = visibility.shown(contact)
	if scope is not None:
		base = base & scope
	rows = (
		frappe.qb.from_(contact)
		.select(contact.value_group, Count("*"))
		.where(base & contact.value_group.isnotnull())
		.groupby(contact.value_group)
		.run()
	)
	scored = frappe.get_all(
		CONTACT,
		filters={"scores_updated_at": ["is", "set"]},
		fields=["scores_updated_at"],
		order_by="scores_updated_at desc",
		limit=1,
	)
	return {
		"groups": {group: cint(total) for group, total in rows if group},
		"engagement": engagement_counts(contact, base),
		"scored_at": str(scored[0].scores_updated_at) if scored else None,
		"purchases": integrations.has_purchases(),
	}
