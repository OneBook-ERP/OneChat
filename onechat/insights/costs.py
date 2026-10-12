import json
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta, timezone

import frappe
import requests
from frappe import _
from frappe.query_builder.functions import Count, IfNull
from frappe.utils import add_days, cint, flt, get_datetime, get_first_day, getdate, now_datetime, today
from pypika.functions import Date

from onechat.workspace import numbers
from onechat.workspace.session import require_admin

MESSAGE = "OneChat Message"
SPEND = "OneChat Spend"
RATE = "OneChat Message Rate"
ACCOUNT = "OneChat Account"
SETTINGS = "WhatsApp Settings"
CATEGORIES = ("marketing", "utility", "authentication", "service")
SYNC_DAYS = 3
BACKFILL_DAYS = 90
RATE_DAYS = 30
THRESHOLDS = (80, 100)
TOP = 10
TIMEOUT = 60
STORE = "Store in OneChat"
LIVE = "Fetch live from Meta"
LIVE_TTL = 600
WINDOW_DAYS = 90
META_DAYS = 365
TEMPLATE_DAYS = 89
TEMPLATE_BATCH = 10
TEMPLATE_TTL = 1800


def country_of(number):
	try:
		import phonenumbers
	except ImportError:
		return None

	digits = "".join(ch for ch in str(number or "") if ch.isdigit())
	if not digits:
		return None
	try:
		return phonenumbers.region_code_for_number(phonenumbers.parse(f"+{digits}")) or None
	except phonenumbers.NumberParseException:
		return None


def record_pricing(doc, status):
	pricing = status.get("pricing") or {}
	if not pricing or doc.get("pricing_category"):
		return False

	billable = bool(pricing.get("billable"))
	doc.billable = 1 if billable else 0
	doc.pricing_category = (pricing.get("category") or "").lower() or None
	doc.pricing_type = (pricing.get("type") or ("regular" if billable else "free")).lower()
	doc.pricing_country = country_of(doc.get("to"))
	return True


def announce(doc):
	if doc.billable:
		frappe.publish_realtime(
			"onechat_cost",
			{"category": doc.pricing_category, "country": doc.pricing_country},
			room="doctype:OneChat Contact",
			after_commit=True,
		)


def utc_start(day):
	return int(datetime.combine(getdate(day), time(), tzinfo=timezone.utc).timestamp())


def graph(account, path, params=None, url=None):
	response = requests.get(
		url or f"{account.url}/{account.version}/{path}",
		params=params,
		headers={"Authorization": f"Bearer {account.get_password('token')}"},
		timeout=TIMEOUT,
	)
	try:
		body = response.json()
	except ValueError:
		body = {}
	if not response.ok:
		raise frappe.ValidationError(meta_message(body, response))
	return body


def meta_message(body, response):
	error = body.get("error") or {}
	message = error.get("message") or response.text[:300]
	if error.get("code") and f"(#{error['code']})" not in message:
		message = f"(#{error['code']}) {message}"
	return message


def paged(account, body, key):
	points = []
	block = body.get(key) or {}
	while block:
		for row in block.get("data") or []:
			points += row.get("data_points") or []
		following = (block.get("paging") or {}).get("next")
		block = graph(account, None, url=following) if following else None
	return points


def point_day(point):
	return datetime.fromtimestamp(cint(point.get("start")), tz=timezone.utc).date()


def pricing_points(account, start, end):
	field = (
		f"pricing_analytics.start({start}).end({end}).granularity(DAILY)"
		'.dimensions(["PRICING_CATEGORY","PRICING_TYPE","COUNTRY","PHONE","TIER"])'
	)
	body = graph(account, account.business_id, {"fields": field})
	points = [
		{
			"date": point_day(point),
			"country": point.get("country"),
			"category": (point.get("pricing_category") or "").lower(),
			"pricing_type": (point.get("pricing_type") or "").lower(),
			"phone": point.get("phone") or "",
			"tier": point.get("tier") or "",
			"volume": cint(point.get("volume")),
			"cost": flt(point.get("cost")),
		}
		for point in paged(account, body, "pricing_analytics")
	]
	return own_number(account, points)


def digits(value):
	return "".join(ch for ch in str(value or "") if ch.isdigit())


def own_number(account, points):
	mine = digits(account.get("display_phone_number"))
	if not mine or not any(point["phone"] for point in points):
		return points
	return [point for point in points if not point["phone"] or digits(point["phone"]).endswith(mine[-10:])]


def cost_hidden(rows):
	paid = [row for row in rows if (row["pricing_type"] or "regular") == "regular" and row["volume"] > 0]
	return bool(paid) and not any(flt(row["cost"]) for row in paid)


CREDIT_LINE = "Meta does not report cost for this number, usually because a Solution Partner bills you on their credit line. Costs here are estimated from your rates."


def spend_note(rows):
	return _(CREDIT_LINE) if cost_hidden(rows) else None


def conversation_points(account, start, end):
	field = (
		f"conversation_analytics.start({start}).end({end}).granularity(DAILY)"
		'.metric_types(["COST","CONVERSATION"]).dimensions(["CONVERSATION_CATEGORY","CONVERSATION_TYPE","COUNTRY"])'
	)
	body = graph(account, account.business_id, {"fields": field})
	return [
		{
			"date": point_day(point),
			"country": point.get("country"),
			"category": (point.get("conversation_category") or "").lower(),
			"pricing_type": (point.get("conversation_type") or "").lower(),
			"volume": cint(point.get("conversation")),
			"cost": flt(point.get("cost")),
		}
		for point in paged(account, body, "conversation_analytics")
	]


def spend_accounts(mode):
	fields = ["name", "spend_synced_at"]
	per_account = frappe.get_meta(ACCOUNT).has_field("spend_storage")
	if per_account:
		fields.append("spend_storage")
	rows = frappe.get_all(
		ACCOUNT, filters={"status": ["!=", "Inactive"], "business_id": ["is", "set"]}, fields=fields
	)
	return [row for row in rows if ((row.get("spend_storage") if per_account else None) or STORE) == mode]


def connected(account):
	return bool(account.business_id and account.get_password("token", raise_exception=False))


def date_span(first):
	return max((getdate(today()) - getdate(first)).days, 1)


def window_points(account, start, end):
	try:
		return pricing_points(account, start, end)
	except frappe.ValidationError:
		return conversation_points(account, start, end)


def fetch_account(account, first):
	currency = (
		graph(account, account.business_id, {"fields": "currency"}).get("currency")
		or account.billing_currency
	)
	now = int(datetime.now(timezone.utc).timestamp())
	points, failures, cursor = [], [], max(getdate(first), getdate(add_days(today(), -META_DAYS)))
	while utc_start(cursor) < now:
		stop = min(utc_start(add_days(cursor, WINDOW_DAYS)), now)
		try:
			points += window_points(account, utc_start(cursor), stop)
		except frappe.ValidationError as error:
			failures.append(error)
		cursor = getdate(add_days(cursor, WINDOW_DAYS))
	if failures and not points and len(failures) * WINDOW_DAYS >= date_span(first):
		raise failures[-1]

	totals = defaultdict(lambda: [0, 0.0])
	for point in points:
		key = (
			point["date"],
			point["country"],
			point["category"],
			point["pricing_type"],
			point.get("phone") or "",
			point.get("tier") or "",
		)
		totals[key][0] += point["volume"]
		totals[key][1] += point["cost"]

	rows = [
		{
			"whatsapp_account": account.name,
			"date": day,
			"country": country,
			"category": category,
			"pricing_type": pricing_type,
			"phone": phone,
			"tier": tier,
			"volume": volume,
			"cost": cost,
			"currency": currency,
		}
		for (day, country, category, pricing_type, phone, tier), (volume, cost) in totals.items()
	]
	return currency, rows


def sync_account(name, days):
	account = frappe.get_doc(ACCOUNT, name)
	if not connected(account):
		return

	first = getdate(add_days(today(), -days))
	try:
		currency, rows = fetch_account(account, first)
		frappe.db.delete(SPEND, {"whatsapp_account": name, "date": [">=", first]})
		for row in rows:
			frappe.get_doc({"doctype": SPEND, **row}).insert(ignore_permissions=True)
		frappe.db.set_value(
			ACCOUNT,
			name,
			{
				"billing_currency": currency,
				"spend_synced_at": now_datetime(),
				"spend_sync_error": spend_note(rows),
			},
			update_modified=False,
		)
	except Exception as error:
		frappe.db.set_value(ACCOUNT, name, "spend_sync_error", str(error)[:500], update_modified=False)
		frappe.log_error(title=f"OneChat spend sync: {name}")
	frappe.db.commit()


def live_accounts():
	return [row.name for row in spend_accounts(LIVE)]


def live_key(name):
	return f"onechat_live_spend:{name}"


def live_rows(name, first):
	cached = frappe.cache().get_value(live_key(name))
	if cached and cached["first"] <= first:
		return cached["rows"]

	account = frappe.get_doc(ACCOUNT, name)
	if not connected(account):
		return []
	start = min(first, cached["first"]) if cached else first
	try:
		currency, rows = fetch_account(account, start)
	except Exception as error:
		frappe.db.set_value(ACCOUNT, name, "spend_sync_error", str(error)[:500], update_modified=False)
		frappe.log_error(title=f"OneChat live spend: {name}")
		return cached["rows"] if cached else []
	frappe.db.set_value(
		ACCOUNT,
		name,
		{
			"billing_currency": currency,
			"spend_synced_at": now_datetime(),
			"spend_sync_error": spend_note(rows),
		},
		update_modified=False,
	)
	frappe.cache().set_value(live_key(name), {"first": start, "rows": rows}, expires_in_sec=LIVE_TTL)
	return rows


def forget_live(names=None):
	for name in names or frappe.get_all(ACCOUNT, pluck="name"):
		frappe.cache().delete_value(live_key(name))


def sync_all():
	for account in spend_accounts(STORE):
		sync_account(account.name, SYNC_DAYS if account.spend_synced_at else BACKFILL_DAYS)
	learn_rates()
	check_budget()


def rate_rows():
	totals = defaultdict(lambda: [0.0, 0])
	for row in actual_rows(add_days(today(), -RATE_DAYS), now_datetime()):
		if flt(row.cost) > 0 and cint(row.volume) > 0 and (row.pricing_type or "") in ("", "regular"):
			totals[(row.country, row.category, row.currency)][0] += flt(row.cost)
			totals[(row.country, row.category, row.currency)][1] += cint(row.volume)
	return [
		frappe._dict(country=country, category=category, currency=code, cost=cost, volume=volume)
		for (country, category, code), (cost, volume) in totals.items()
	]


def learn_rates():
	rows = rate_rows()
	existing = {
		(row.country, row.category): row
		for row in frappe.get_all(RATE, fields=["name", "country", "category", "source"])
	}
	for row in rows:
		if not row.country or row.category not in CATEGORIES:
			continue
		rate = round(flt(row.cost) / cint(row.volume), 6)
		current = existing.get((row.country.upper(), row.category))
		if current and current.source == "Manual":
			continue
		if current:
			frappe.db.set_value(
				RATE, current.name, {"rate": rate, "currency": row.currency}, update_modified=False
			)
		else:
			frappe.get_doc(
				{
					"doctype": RATE,
					"country": row.country,
					"category": row.category,
					"rate": rate,
					"currency": row.currency,
					"source": "Meta",
				}
			).insert(ignore_permissions=True)
	frappe.db.commit()


def rate_table():
	rates = {}
	for row in frappe.get_all(RATE, fields=["country", "category", "rate"]):
		rates[((row.country or "*").upper(), row.category)] = flt(row.rate)
	return rates


def price(rates, country, category):
	return rates.get(((country or "").upper(), category), rates.get(("*", category)))


def billable_rows(since, until, extra=None):
	message = frappe.qb.DocType(MESSAGE)
	day = Date(message.creation)
	columns = [
		message.whatsapp_account.as_("account"),
		day.as_("day"),
		message.pricing_country.as_("country"),
		message.pricing_category.as_("category"),
	]
	groups = [message.whatsapp_account, day, message.pricing_country, message.pricing_category]
	for alias, column in (extra or {}).items():
		columns.append(column.as_(alias))
		groups.append(column)
	return (
		frappe.qb.from_(message)
		.select(*columns, Count("*").as_("count"))
		.where(
			shown(
				message, (message.billable == 1) & (message.creation >= since) & (message.creation <= until)
			)
		)
		.groupby(*groups)
		.run(as_dict=True)
	)


def shown(table, condition):
	part = numbers.condition(table)
	return condition if part is None else condition & part


def actual_rows(since, until):
	first, last = getdate(since), getdate(until)
	off = set(numbers.hidden())
	live = [
		frappe._dict(row)
		for name in live_accounts()
		if name not in off
		for row in live_rows(name, first)
		if first <= getdate(row["date"]) <= last
	]

	filters = {"date": ["between", [first, last]]}
	if off:
		filters["whatsapp_account"] = ["not in", list(off)]
	fields = ["whatsapp_account", "date", "country", "category", "pricing_type", "volume", "cost", "currency"]
	if frappe.get_meta(SPEND).has_field("tier"):
		fields += ["phone", "tier"]
	stored = frappe.get_all(SPEND, filters=filters, fields=fields)
	return stored + live


def by_number(rows):
	labels = dict(frappe.get_all(ACCOUNT, fields=["name", "account_name"], as_list=True))
	totals = defaultdict(lambda: [0.0, 0])
	for row in rows:
		totals[row.whatsapp_account][0] += flt(row.cost)
		totals[row.whatsapp_account][1] += cint(row.volume)
	out = [
		{"key": name, "name": labels.get(name) or name, "cost": round(cost, 4), "messages": count}
		for name, (cost, count) in totals.items()
	]
	return sorted(out, key=lambda row: row["cost"], reverse=True)


def current_tiers(rows):
	latest = {}
	for row in rows:
		tier = row.get("tier")
		if not tier or row.category not in ("utility", "authentication"):
			continue
		key = (row.whatsapp_account, row.category)
		if key not in latest or getdate(row.date) >= getdate(latest[key]["date"]):
			latest[key] = {"date": row.date, "tier": tier}
	labels = dict(frappe.get_all(ACCOUNT, fields=["name", "account_name"], as_list=True))
	return [
		{"account": labels.get(account) or account, "category": category, "tier": value["tier"]}
		for (account, category), value in sorted(latest.items())
	]


def post(account, path, params):
	response = requests.post(
		f"{account.url}/{account.version}/{path}",
		params=params,
		headers={"Authorization": f"Bearer {account.get_password('token')}"},
		timeout=TIMEOUT,
	)
	if not response.ok:
		try:
			body = response.json()
		except ValueError:
			body = {}
		raise frappe.ValidationError(meta_message(body, response))


FULL_METRICS = ["COST", "SENT", "DELIVERED", "READ", "CLICKED"]
BASIC_METRICS = ["SENT", "DELIVERED", "READ"]
INSIGHTS_ENABLED = "onechat:template-insights-enabled:{0}"
BASIC_ONLY = "onechat:template-insights-basic:{0}"


def fetch_template_analytics(account, ids, start, end, metrics):
	params = {
		"start": str(start),
		"end": str(end),
		"granularity": "DAILY",
		"template_ids": json.dumps(ids),
		"metric_types": json.dumps(metrics),
	}
	return graph(account, f"{account.business_id}/template_analytics", params)


def template_points(account, ids, start, end, notes=None):
	basic_key = BASIC_ONLY.format(account.name)
	metrics = BASIC_METRICS if frappe.cache().get_value(basic_key) else FULL_METRICS
	try:
		body = fetch_template_analytics(account, ids, start, end, metrics)
	except frappe.ValidationError as first:
		enabled_key = INSIGHTS_ENABLED.format(account.name)
		body = None
		if not frappe.cache().get_value(enabled_key):
			try:
				post(account, account.business_id, {"is_enabled_for_insights": "true"})
				frappe.cache().set_value(enabled_key, 1, expires_in_sec=86400)
				body = fetch_template_analytics(account, ids, start, end, metrics)
			except frappe.ValidationError:
				body = None
		if body is None and metrics != BASIC_METRICS:
			try:
				body = fetch_template_analytics(account, ids, start, end, BASIC_METRICS)
				frappe.cache().set_value(basic_key, 1, expires_in_sec=86400)
			except frappe.ValidationError:
				raise first
		if body is None:
			raise first
	if frappe.cache().get_value(basic_key) and notes is not None:
		notes.add(account.name)
	points = []
	for block in body.get("data") or []:
		points += block.get("data_points") or []
	return points


def template_stats(since, until):
	first = max(getdate(since), getdate(add_days(today(), -TEMPLATE_DAYS)))
	last = min(getdate(until), getdate(today()))
	if first > last:
		return [], None
	message = frappe.qb.DocType(MESSAGE)
	used = set(
		frappe.qb.from_(message)
		.select(message.template)
		.where(message.template.isnotnull() & (message.creation >= since) & (message.creation <= until))
		.distinct()
		.run(pluck=True)
	)
	if not used:
		return [], None

	off = set(numbers.hidden())
	out, problem, basic = {}, None, set()
	for account_name in frappe.get_all(
		ACCOUNT, filters={"status": ["!=", "Inactive"], "business_id": ["is", "set"]}, pluck="name"
	):
		if account_name in off:
			continue
		templates = frappe.get_all(
			"WhatsApp Templates",
			filters={"whatsapp_account": account_name, "id": ["is", "set"], "name": ["in", list(used)]},
			fields=["name", "template_name", "id"],
		)
		if not templates:
			continue
		key = f"onechat:template-analytics:{account_name}:{first}:{last}:{','.join(sorted(row.id for row in templates))}"
		cached = frappe.cache().get_value(key)
		if cached is None:
			account = frappe.get_doc(ACCOUNT, account_name)
			if not connected(account):
				continue
			cached = []
			try:
				for index in range(0, len(templates), TEMPLATE_BATCH):
					cached += template_points(
						account,
						[row.id for row in templates[index : index + TEMPLATE_BATCH]],
						first,
						last,
						basic,
					)
			except Exception as error:
				problem = _("Template analytics from Meta: {0}").format(str(error)[:200])
				frappe.log_error(title=f"OneChat template analytics: {account_name}")
				continue
			frappe.cache().set_value(key, cached, expires_in_sec=TEMPLATE_TTL)
		if frappe.cache().get_value(BASIC_ONLY.format(account_name)):
			basic.add(account_name)
		names = {row.id: row for row in templates}
		for point in cached:
			row = names.get(str(point.get("template_id")))
			if not row:
				continue
			entry = out.setdefault(
				row.name,
				{
					"key": row.name,
					"name": row.template_name or row.name,
					"sent": 0,
					"delivered": 0,
					"read": 0,
					"clicked": 0,
					"cost": 0.0,
				},
			)
			entry["sent"] += cint(point.get("sent"))
			entry["delivered"] += cint(point.get("delivered"))
			entry["read"] += cint(point.get("read"))
			entry["clicked"] += sum(cint(item.get("count")) for item in point.get("clicked") or [])
			entry["cost"] += sum(
				flt(item.get("value"))
				for item in point.get("cost") or []
				if item.get("type") == "amount_spent"
			)
	rows = sorted(out.values(), key=lambda row: (row["cost"], row["sent"]), reverse=True)
	for row in rows:
		row["cost"] = round(row["cost"], 4)
		row["read_rate"] = round(row["read"] * 100 / row["delivered"], 1) if row["delivered"] else None
	if basic and not problem:
		problem = _(
			"Template analytics from Meta: cost and clicks aren't available for {0}, usually because WhatsApp is billed through a partner. Sends, deliveries and reads still show."
		).format(", ".join(sorted(basic)))
	return rows[:TOP], problem


def spend_between(since, until, rates=None):
	rates = rates if rates is not None else rate_table()
	actual = actual_rows(since, until)
	covered = {(row.whatsapp_account, getdate(row.date)) for row in actual}
	days = defaultdict(lambda: {"cost": defaultdict(float), "estimated": False, "actual": False})
	countries, categories = Counter(), Counter()
	unpriced = 0
	estimated_total = 0.0

	for row in actual:
		day = days[getdate(row.date)]
		day["actual"] = True
		day["cost"][row.category or "other"] += flt(row.cost)
		countries[row.country or "?"] += flt(row.cost)
		categories[row.category or "other"] += flt(row.cost)

	for row in billable_rows(since, until):
		key_day = getdate(row.day)
		if (row.account, key_day) in covered:
			continue
		rate = price(rates, row.country, row.category)
		if rate is None:
			unpriced += cint(row.count)
			continue
		cost = rate * cint(row.count)
		day = days[key_day]
		day["estimated"] = True
		day["cost"][row.category or "other"] += cost
		countries[row.country or "?"] += cost
		categories[row.category or "other"] += cost
		estimated_total += cost

	total = sum(categories.values())
	return frappe._dict(
		days=days,
		countries=countries,
		categories=categories,
		total=total,
		estimated=estimated_total,
		unpriced=unpriced,
	)


def currency():
	values = [
		row
		for row in frappe.get_all(
			ACCOUNT, filters={"billing_currency": ["is", "set"]}, pluck="billing_currency"
		)
	]
	values += frappe.get_all(RATE, filters={"currency": ["is", "set"]}, pluck="currency", limit=1)
	return values[0] if values else "USD"


def message_counts(since, until):
	message = frappe.qb.DocType(MESSAGE)
	kind = IfNull(message.pricing_type, "")
	rows = (
		frappe.qb.from_(message)
		.select(kind.as_("kind"), Count("*").as_("count"))
		.where(
			shown(
				message,
				(message.type == "Outgoing")
				& message.pricing_category.isnotnull()
				& (message.creation >= since)
				& (message.creation <= until),
			)
		)
		.groupby(kind)
		.run(as_dict=True)
	)
	return {row.kind or "unknown": cint(row.count) for row in rows}


def estimated_by(rates, since, until, alias, column, labels=None):
	totals = defaultdict(lambda: [0.0, 0])
	for row in billable_rows(since, until, {alias: column}):
		rate = price(rates, row.country, row.category)
		key = row.get(alias) or ""
		totals[key][1] += cint(row.count)
		if rate is not None:
			totals[key][0] += rate * cint(row.count)
	rows = [
		{
			"key": key,
			"name": (labels or {}).get(key, key) or _("Other"),
			"cost": round(cost, 4),
			"messages": count,
		}
		for key, (cost, count) in totals.items()
	]
	return sorted(rows, key=lambda row: (row["cost"], row["messages"]), reverse=True)[:TOP]


def budget_state(rates):
	budget = (
		flt(frappe.db.get_single_value(SETTINGS, "monthly_budget"))
		if frappe.get_meta(SETTINGS).has_field("monthly_budget")
		else 0
	)
	start = get_datetime(get_first_day(today()))
	month = spend_between(start, now_datetime(), rates)
	return {
		"spend": round(month.total, 4),
		"budget": budget,
		"percent": round(month.total * 100 / budget, 1) if budget else None,
	}


def admins():
	users = frappe.get_all(
		"Has Role",
		filters={"role": ["in", ["OneChat Admin", "System Manager"]], "parenttype": "User"},
		pluck="parent",
	)
	enabled = frappe.get_all(
		"User",
		filters={"name": ["in", list(set(users)) or [""]], "enabled": 1, "user_type": "System User"},
		pluck="name",
	)
	return [user for user in enabled if user not in ("Administrator", "Guest")]


def check_budget():
	state = budget_state(rate_table())
	if not state["budget"]:
		return

	month = today()[:7]
	sent = set(frappe.parse_json(frappe.db.get_single_value(SETTINGS, "budget_alerts") or "[]") or [])
	for threshold in THRESHOLDS:
		key = f"{month}:{threshold}"
		if state["percent"] < threshold or key in sent:
			continue
		subject = _("WhatsApp spend has reached {0}% of this month's budget ({1} of {2} {3}).").format(
			threshold, round(state["spend"], 2), state["budget"], currency()
		)
		for user in admins():
			frappe.get_doc(
				{
					"doctype": "Notification Log",
					"subject": subject,
					"for_user": user,
					"type": "Alert",
					"document_type": SETTINGS,
					"document_name": SETTINGS,
				}
			).insert(ignore_permissions=True)
		sent.add(key)
	frappe.db.set_single_value(SETTINGS, "budget_alerts", json.dumps(sorted(sent)[-24:]))
	frappe.db.commit()


def costs(span):
	earliest = min(getdate(span.previous), getdate(get_first_day(today())))
	for name in live_accounts():
		if name not in numbers.hidden():
			live_rows(name, earliest)
	rates = rate_table()
	now = spend_between(span.since, span.until, rates)
	before = spend_between(span.previous, span.since, rates)
	counts = message_counts(span.since, span.until)
	paid = sum(
		value
		for key, value in counts.items()
		if key not in ("free_customer_service", "free_entry_point", "free")
	)
	free = sum(counts.values()) - paid

	actual = actual_rows(span.since, span.until)
	meta_templates, template_problem = template_stats(span.since, span.until)
	first, last = getdate(span.since), getdate(span.until)
	timeline = []
	cursor = first
	while cursor <= last:
		day = now.days.get(cursor) or {"cost": {}, "estimated": False, "actual": False}
		timeline.append(
			{
				"at": str(cursor),
				**{category: round(day["cost"].get(category, 0), 4) for category in CATEGORIES},
				"estimated": day["estimated"] and not day["actual"],
				"mixed": day["estimated"] and day["actual"],
			}
		)
		cursor += timedelta(days=1)

	message = frappe.qb.DocType(MESSAGE)
	templates = estimated_by(rates, span.since, span.until, "template", message.template)
	template_names = dict(
		frappe.get_all(
			"WhatsApp Templates",
			filters={"name": ["in", [row["key"] for row in templates] or [""]]},
			fields=["name", "template_name"],
			as_list=True,
		)
	)
	for row in templates:
		row["name"] = template_names.get(row["key"], row["key"]) or _("Not a template")

	broadcasts = estimated_by(rates, span.since, span.until, "broadcast", message.bulk_message_reference)
	titles = dict(
		frappe.get_all(
			"Bulk WhatsApp Message",
			filters={"name": ["in", [row["key"] for row in broadcasts] or [""]]},
			fields=["name", "title"],
			as_list=True,
		)
	)
	broadcasts = [dict(row, name=titles.get(row["key"]) or row["key"]) for row in broadcasts if row["key"]]

	accounts = frappe.get_all(
		ACCOUNT,
		filters={"business_id": ["is", "set"]},
		fields=["name", "account_name", "spend_synced_at", "spend_sync_error"],
	)
	return {
		"currency": currency(),
		"summary": {
			"spend": round(now.total, 4),
			"previous": round(before.total, 4),
			"estimated": round(now.estimated, 4),
			"paid": paid,
			"free": free,
			"per_message": round(now.total / paid, 4) if paid else None,
			"unpriced": now.unpriced,
		},
		"month": budget_state(rates),
		"days": timeline,
		"categories": [
			{"name": key, "value": round(value, 4)} for key, value in now.categories.most_common() if value
		],
		"countries": [
			{"name": key, "value": round(value, 4)} for key, value in now.countries.most_common(TOP) if value
		],
		"senders": estimated_by(rates, span.since, span.until, "sender", IfNull(message.source, "")),
		"templates": templates,
		"meta_templates": meta_templates,
		"template_problem": template_problem,
		"numbers": by_number(actual),
		"tiers": current_tiers(actual),
		"meta_limited": getdate(span.since) < getdate(add_days(today(), -META_DAYS)),
		"broadcasts": broadcasts,
		"free": counts,
		"rates": frappe.get_all(
			RATE,
			fields=["name", "country", "category", "rate", "currency", "source"],
			order_by="country asc, category asc",
		),
		"sync": [
			{
				"account": row.account_name or row.name,
				"synced_at": row.spend_synced_at,
				"error": row.spend_sync_error,
			}
			for row in accounts
		],
		"live": live_accounts(),
	}


@frappe.whitelist(methods=["POST"])
def sync_now():
	require_admin()
	forget_live(live_accounts())
	if not spend_accounts(STORE):
		return _("Fetching fresh spend from Meta.")
	frappe.enqueue(
		"onechat.insights.costs.sync_all", queue="long", job_id="onechat_spend_sync", deduplicate=True
	)
	return _("Fetching spend from Meta. This takes a minute.")


@frappe.whitelist()
def save_rate(country: str, category: str, rate: float | int | str, name: str | None = None):
	require_admin()
	if category not in CATEGORIES:
		frappe.throw(_("Pick a category."))
	values = {
		"country": country,
		"category": category,
		"rate": flt(rate),
		"source": "Manual",
		"currency": currency(),
	}
	if name:
		doc = frappe.get_doc(RATE, name)
		doc.update(values)
		doc.save(ignore_permissions=True)
	else:
		frappe.get_doc({"doctype": RATE, **values}).insert(ignore_permissions=True)
	return frappe.get_all(
		RATE,
		fields=["name", "country", "category", "rate", "currency", "source"],
		order_by="country asc, category asc",
	)


@frappe.whitelist()
def delete_rate(name: str):
	require_admin()
	frappe.delete_doc(RATE, name, ignore_permissions=True)
	return frappe.get_all(
		RATE,
		fields=["name", "country", "category", "rate", "currency", "source"],
		order_by="country asc, category asc",
	)


@frappe.whitelist(methods=["POST"])
def set_storage(account: str, mode: str):
	require_admin()
	if mode not in (STORE, LIVE):
		frappe.throw(_("Pick how spend data is kept."))
	if not frappe.get_meta(ACCOUNT).has_field("spend_storage"):
		frappe.throw(_("Run bench migrate to finish setting up spend storage."))

	frappe.db.set_value(
		ACCOUNT, account, {"spend_storage": mode, "spend_synced_at": None}, update_modified=False
	)
	forget_live([account])
	if mode == LIVE:
		frappe.db.delete(SPEND, {"whatsapp_account": account})
		return _("Stored spend for this number deleted. Its costs now come live from Meta.")

	frappe.enqueue(
		"onechat.insights.costs.sync_account",
		queue="long",
		job_id=f"onechat_spend_sync_{account}",
		deduplicate=True,
		enqueue_after_commit=True,
		name=account,
		days=BACKFILL_DAYS,
	)
	return _(
		"Spend for this number is now stored in OneChat. The last {0} days are being fetched from Meta."
	).format(BACKFILL_DAYS)


@frappe.whitelist()
def set_budget(amount: float | int | str):
	require_admin()
	frappe.db.set_single_value(SETTINGS, "monthly_budget", max(flt(amount), 0))
	return budget_state(rate_table())
