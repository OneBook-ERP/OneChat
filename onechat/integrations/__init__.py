import frappe

HOOK = "onechat_integrations"
SETTINGS = "WhatsApp Settings"


def memo():
	cache = getattr(frappe.local, "onechat_integrations", None)
	if cache is None:
		cache = frappe.local.onechat_integrations = {}
	return cache


def forget():
	frappe.local.onechat_integrations = {}


def specs():
	cache = memo()
	if "specs" not in cache:
		cache["specs"] = [frappe.get_attr(path)() for path in frappe.get_hooks(HOOK)]
	return [dict(spec) for spec in cache["specs"]]


def registered():
	cache = memo()
	if "registered" not in cache:
		installed = set(frappe.get_installed_apps())
		out = []
		for spec in specs():
			if spec.get("ready"):
				spec["installed"] = bool(run(spec["ready"]))
			else:
				spec["installed"] = not spec.get("app") or spec["app"] in installed
			out.append(spec)
		cache["registered"] = out
	return [dict(spec) for spec in cache["registered"]]


def setting(fieldname):
	if not frappe.get_meta(SETTINGS).has_field(fieldname):
		return None

	return frappe.db.get_single_value(SETTINGS, fieldname)


def save_setting(fieldname, value):
	if not frappe.get_meta(SETTINGS).has_field(fieldname):
		frappe.throw(frappe._("Run bench migrate to finish setting up OneChat integrations."))

	frappe.db.set_single_value(SETTINGS, fieldname, value)
	forget()


def disabled():
	value = setting("disabled_integrations")

	return set(frappe.parse_json(value) or []) if value else set()


def active():
	off = disabled()

	return [spec for spec in registered() if spec["installed"] and spec["name"] not in off]


def link_doctypes():
	return {
		row["doctype"]: {**row, "integration": spec["name"]}
		for spec in active()
		for row in spec.get("link_doctypes", [])
	}


def run(path, *args):
	return frappe.get_attr(path)(*args) if path else None


def auto_link(contact):
	if not contact.wa_number or setting("disable_auto_link"):
		return []
	from onechat.integrations import links

	have = {(row.doctype, row.name) for row in links.of(contact)}
	found = []
	for spec in active():
		finder = spec.get("find_all_by_phone") or spec.get("find_by_phone")
		if not finder:
			continue
		try:
			result = run(finder, contact.wa_number) or []
		except Exception:
			frappe.log_error(title=f"OneChat auto-link failed: {spec['name']}")
			continue
		matches = result if spec.get("find_all_by_phone") else [result]
		found += [tuple(match) for match in matches if match and tuple(match) not in have]
	return list(dict.fromkeys(found))


def linked(contact, doctype, name):
	if not (doctype and name):
		return
	from onechat.inbox.scores import queue_update

	queue_update(contact)
	for spec in active():
		if owns(spec, doctype) and spec.get("on_link"):
			try:
				run(spec["on_link"], contact, doctype, name)
			except Exception:
				frappe.log_error(title=f"OneChat link hook failed: {spec['name']}")


def linked_specs(contact):
	from onechat.integrations import connection, links
	from onechat.workspace.session import can_read

	specs = {spec["name"]: spec for spec in active()}
	out = []
	for row in links.of(contact):
		spec = specs.get(row.integration)
		if not (spec and row.main and owns(spec, row.doctype)):
			continue
		if not connection.source_for(row.doctype).remote and not can_read(row.doctype, row.name):
			continue
		out.append((spec, row))
	return out


def record_stats(contact):
	out = []
	for spec, row in linked_specs(contact):
		if not spec.get("stats"):
			continue
		try:
			out += [
				{**stat, "integration": spec["name"]}
				for stat in run(spec["stats"], row.doctype, row.name) or []
			]
		except Exception:
			frappe.log_error(title=f"OneChat record stats: {spec['name']}")
	return out


def record_timeline(contact, before, limit):
	out = []
	for spec, row in linked_specs(contact):
		if not spec.get("timeline"):
			continue
		try:
			out += [
				{**event, "integration": spec["name"]}
				for event in run(spec["timeline"], row.doctype, row.name, before, limit) or []
			]
		except Exception:
			frappe.log_error(title=f"OneChat record timeline: {spec['name']}")
	out.sort(key=lambda event: str(event.get("at") or ""), reverse=True)
	return out[: int(limit)] if limit else out


def has_purchases():
	return any(spec.get("metrics") for spec in active())


def metric_doctypes():
	return {
		row["doctype"] for spec in active() if spec.get("metrics") for row in spec.get("link_doctypes", [])
	}


def record_metrics(doctype, names):
	spec = next((spec for spec in active() if owns(spec, doctype) and spec.get("metrics")), None)
	if not spec or not names:
		return {}
	return run(spec["metrics"], doctype, names) or {}


def owns(spec, doctype):
	return doctype in [row["doctype"] for row in spec.get("link_doctypes", [])]


def find(integration):
	return next((spec for spec in active() if spec["name"] == integration), None)


def needs(action, payload=None):
	rule = action.get("needs") or []
	return (run(rule, payload) or []) if isinstance(rule, str) else rule


def permitted(action, payload=None):
	from onechat.integrations import connection
	from onechat.workspace.session import can

	return all(
		connection.source_for(doctype).remote or can(doctype, ptype)
		for doctype, ptype in needs(action, payload)
	)


def require_needs(action, payload=None):
	from onechat.integrations import connection
	from onechat.workspace.session import require

	for doctype, ptype in needs(action, payload):
		if not connection.source_for(doctype).remote:
			require(doctype, ptype)


def row_action(spec, key):
	return next((row for row in (spec or {}).get("row_actions", []) if row["key"] == key), None)


def expand(spec, actions):
	out = []
	for action in actions or []:
		meta = row_action(spec, action) if isinstance(action, str) else action
		if meta:
			out.append({"key": meta["key"], "label": meta.get("label"), "icon": meta.get("icon")})

	return out


def cards(contact):
	out = []
	for spec, row in linked_specs(contact):
		try:
			found = run(spec.get("cards"), row.doctype, row.name) or []
		except Exception:
			frappe.log_error(title=f"OneChat record cards: {spec['name']}")
			continue
		for card in found:
			if card.get("rows"):
				card["rows"] = [
					{**item, "actions": expand(spec, item.get("actions"))} if item.get("actions") else item
					for item in card["rows"]
				]
			out.append({**card, "integration": spec["name"], "link": row.name})

	return out


def actions(contact):
	from onechat.integrations import links

	out = []
	for spec in active():
		if not spec.get("actions"):
			continue
		view = links.view(contact, spec["name"])
		for action in spec["actions"]:
			if not permitted(action) or (action.get("condition") and not run(action["condition"], view)):
				continue
			out.append(
				{
					"integration": spec["name"],
					"key": action["key"],
					"label": action["label"],
					"icon": action.get("icon"),
					"dialog": action.get("dialog"),
				}
			)

	return out


def perform(contact, integration, key, payload=None):
	from onechat.integrations import links

	spec = find(integration)
	action = next((row for row in (spec or {}).get("actions", []) if row["key"] == key), None)
	if not action:
		frappe.throw(frappe._("This action is not available."))
	require_needs(action, payload)
	view = links.view(contact, integration)
	if action.get("condition") and not run(action["condition"], view):
		frappe.throw(frappe._("This action no longer applies to this contact."))

	if payload is None:
		return run(action["method"], view)

	return run(action["method"], view, payload)


def perform_row(contact, integration, key, doctype, name):
	from onechat.integrations import links

	action = row_action(find(integration), key)
	if not action:
		frappe.throw(frappe._("This action is not available."))
	require_needs(action)
	view = links.view(contact, integration)
	if action.get("condition") and not run(action["condition"], view, doctype, name):
		frappe.throw(frappe._("This action no longer applies to {0}.").format(name))

	return run(action["method"], view, doctype, name)
