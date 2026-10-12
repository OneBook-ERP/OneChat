import re

import frappe
from frappe import _

RECORD_STEPS = ("find_record", "create_record", "update_record", "send_to_records")
NO_VALUE = {"Section Break", "Column Break", "Tab Break", "HTML", "Button", "Heading", "Fold", "Image"}
TABLES = {"Table", "Table MultiSelect"}
TEMPLATE = re.compile(r"\{\{.*?\}\}")
COLUMN = re.compile(r"`tab([^`]+)`\.`([^`]+)`")
BROKEN_DEFAULTS = {"Date": "now", "Time": "today"}
DB_ERRORS = {
	1048: "{field} cannot be empty.",
	1292: "{field} got a value that is not a valid date or time: {value}.",
	1366: "{field} got a value of the wrong type: {value}.",
	1406: "The value for {field} is too long.",
}


def source_of(doctype):
	from onechat.integrations.connection import source_for

	return source_for(doctype)


def fields_of(doctype, source=None):
	source = source or source_of(doctype)
	if source.remote:
		rows = source.meta_fields(doctype)
	else:
		rows = [
			{
				"fieldname": df.fieldname,
				"label": df.label or df.fieldname,
				"fieldtype": df.fieldtype,
				"options": df.options,
				"reqd": df.reqd,
				"default": df.default,
				"read_only": df.read_only,
			}
			for df in frappe.get_meta(doctype).fields
		]
	return {
		row["fieldname"]: row for row in rows if row.get("fieldname") and row.get("fieldtype") not in NO_VALUE
	}


def label_of(fields, fieldname):
	row = fields.get(fieldname) or {}
	return _(row.get("label") or fieldname)


def literal(value):
	return isinstance(value, str) and not TEMPLATE.search(value)


def empty(value):
	return value is None or (isinstance(value, str) and not value.strip())


def broken_default(row):
	default = str(row.get("default") or "").strip().lower()
	return bool(default) and BROKEN_DEFAULTS.get(row.get("fieldtype")) == default


def missing_required(fields, values):
	missing = []
	for fieldname, row in fields.items():
		if not row.get("reqd") or row.get("read_only") or row.get("fieldtype") in TABLES:
			continue
		if not empty(values.get(fieldname)):
			continue
		if row.get("default") not in (None, ""):
			continue
		missing.append(fieldname)
	return missing


def issue(level, message, node_id=None):
	return {"level": level, "message": message, "node_id": node_id}


def check_record_step(node_id, name, kind, config):
	out = []
	doctype = config.get("doctype")
	if not doctype:
		return out

	try:
		source = source_of(doctype)
		if not source.has_doctype(doctype):
			return [
				issue(
					"error",
					_("{0}: {1} does not exist on the connected site.").format(name, doctype),
					node_id,
				)
			]
		fields = fields_of(doctype, source)
	except Exception as error:
		return [
			issue("warning", _("{0}: could not check {1}: {2}").format(name, doctype, str(error)), node_id)
		]

	values = config.get("fields") or {}
	known = set(fields) | {"name"}

	for fieldname in values:
		if fieldname and fieldname not in known:
			out.append(
				issue(
					"error",
					_("{0}: {1} has no field called {2}. It may have been renamed or removed.").format(
						name, doctype, fieldname
					),
					node_id,
				)
			)

	for key in ("field", "phone_field", "match_field"):
		fieldname = config.get(key)
		if fieldname and fieldname not in known:
			out.append(
				issue(
					"error", _("{0}: {1} has no field called {2}.").format(name, doctype, fieldname), node_id
				)
			)

	for fieldname, value in values.items():
		row = fields.get(fieldname)
		if not row or not literal(value) or empty(value):
			continue
		if row.get("fieldtype") == "Select":
			options = [option for option in str(row.get("options") or "").split("\n") if option]
			if options and value not in options:
				out.append(
					issue(
						"error",
						_("{0}: {1} must be one of {2}, not {3}.").format(
							name, label_of(fields, fieldname), ", ".join(options), value
						),
						node_id,
					)
				)
		elif row.get("fieldtype") == "Link" and row.get("options"):
			try:
				if not source.exists(row["options"], value):
					out.append(
						issue(
							"warning",
							_("{0}: {1} {2} does not exist yet.").format(name, _(row["options"]), value),
							node_id,
						)
					)
			except Exception:
				pass

	if kind == "create_record":
		for fieldname in missing_required(fields, values):
			out.append(
				issue(
					"error",
					_("{0}: {1} needs {2}, but this step does not fill it.").format(
						name, doctype, label_of(fields, fieldname)
					),
					node_id,
				)
			)
		for fieldname, row in fields.items():
			if row.get("reqd") and row.get("fieldtype") in TABLES and fieldname not in values:
				out.append(
					issue(
						"error",
						_("{0}: {1} needs at least one row in {2}, which this step cannot add.").format(
							name, doctype, label_of(fields, fieldname)
						),
						node_id,
					)
				)
			if broken_default(row) and fieldname not in values:
				out.append(
					issue(
						"error",
						_(
							'{0}: the field {2} on {1} has the default "{3}", which Frappe cannot save from the server. Change it to {4} in Customize Form, or fill it in this step.'
						).format(
							name,
							doctype,
							label_of(fields, fieldname),
							row.get("default"),
							"Today" if row.get("fieldtype") == "Date" else "Now",
						),
						node_id,
					)
				)

	if source.remote:
		try:
			source.get_list(doctype, fields=["name"], limit=1)
		except Exception as error:
			out.append(
				issue(
					"error",
					_("{0}: the API user on {1} cannot read {2}: {3}").format(
						name, source.site.label, doctype, str(error)
					),
					node_id,
				)
			)
	return out


def check_graph(graph):
	out = []
	for node_id, node in graph.nodes.items():
		kind = graph.kind(node)
		if kind not in RECORD_STEPS:
			continue
		data = node.get("data") or {}
		name = data.get("label") or kind.replace("_", " ").capitalize()
		out.extend(check_record_step(node_id, name, kind, graph.config(node)))
	return out


def fieldnames_in(text):
	return [part.strip() for part in re.split(r"[,\s]+", text) if part.strip()]


def friendly(error, doctype=None):
	from onechat.integrations.connection import RemoteError

	fields = {}
	if doctype:
		try:
			fields = fields_of(doctype)
		except Exception:
			fields = {}
	text = frappe.utils.strip_html(str(error) or error.__class__.__name__).strip()

	if isinstance(error, frappe.MandatoryError):
		names = fieldnames_in(text.split("]:", 1)[-1]) if "]:" in text else []
		labels = ", ".join(label_of(fields, name) for name in names) or text
		return _("{0} could not be saved because these are empty: {1}.").format(
			_(doctype or _("The record")), labels
		), _("Fill them in this step, or give them a default in Customize Form.")
	if isinstance(error, frappe.DuplicateEntryError | frappe.UniqueValidationError):
		return _("A {0} with the same details already exists.").format(_(doctype or _("record"))), _(
			'Set "If it already exists" on this step to update or reuse the existing record.'
		)
	if isinstance(error, frappe.PermissionError):
		return _("Not allowed: {0}").format(text), _(
			"Give the user the flow runs as the right role, or check the API user on the connected site."
		)
	if isinstance(error, frappe.LinkValidationError):
		return text, _("Create the linked record first, or map a value that exists.")
	if isinstance(error, frappe.CharacterLengthExceededError):
		return text, _("Shorten the value in this step.")
	if isinstance(error, RemoteError):
		hint = (
			_("The connected site did not answer. OneChat tried again before giving up.")
			if error.transient
			else None
		)
		return text, hint

	code = error.args[0] if getattr(error, "args", None) and isinstance(error.args[0], int) else None
	if code in DB_ERRORS:
		match = COLUMN.search(text)
		fieldname = match.group(2) if match else None
		table = match.group(1) if match else doctype
		if table and table != doctype:
			try:
				fields = fields_of(table)
			except Exception:
				fields = {}
		value = re.search(r"value: '([^']*)'", text)
		message = _(DB_ERRORS[code]).format(
			field=label_of(fields, fieldname) if fieldname else _("A field"),
			value=value.group(1) if value else "",
		)
		row = fields.get(fieldname) or {}
		hint = (
			_('Its default in Customize Form is "{0}". Change it to {1}.').format(
				row.get("default"), "Today" if row.get("fieldtype") == "Date" else "Now"
			)
			if broken_default(row)
			else _("Check the value this step sends for it, and its default in Customize Form.")
		)
		return f"{_(table or '')}: {message}".strip(": "), hint

	return text, None


def transient(error):
	from onechat.integrations.connection import RemoteError

	return isinstance(error, RemoteError) and error.transient
