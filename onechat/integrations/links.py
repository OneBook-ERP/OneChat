import copy

import frappe
from frappe.utils import cint

from onechat import integrations

CONTACT = "OneChat Contact"
LINK = "OneChat Contact Link"
TITLE_TTL = 600
TITLES = {
	"Customer": ("customer_name", None),
	"Lead": ("lead_name", "status"),
	"Supplier": ("supplier_name", None),
	"CRM Lead": ("lead_name", "status"),
	"CRM Deal": ("organization", "status"),
}


def owner(doctype):
	for spec in integrations.specs():
		if integrations.owns(spec, doctype):
			return spec["name"]
	return None


def stored_rows(contact):
	return frappe.get_all(
		LINK,
		filters={"parent": contact, "parenttype": CONTACT, "parentfield": "links"},
		fields=["name", "integration", "link_doctype", "link_name", "main"],
		order_by="idx asc",
	)


def of(contact):
	if isinstance(contact, str):
		doc = frappe.db.get_value(
			CONTACT, contact, ["name", "reference_doctype", "reference_docname"], as_dict=True
		)
		if not doc:
			return []
		stored = stored_rows(contact)
	else:
		doc = contact
		stored = contact.get("links") or []

	out = []
	for row in stored:
		if (
			row.link_doctype
			and row.link_name
			and not any((item.doctype, item.name) == (row.link_doctype, row.link_name) for item in out)
		):
			out.append(entry(row.integration, row.link_doctype, row.link_name, doc, cint(row.get("main"))))
	if doc.reference_doctype and doc.reference_docname:
		integration = owner(doc.reference_doctype)
		if integration and not any(
			(item.doctype, item.name) == (doc.reference_doctype, doc.reference_docname) for item in out
		):
			out.insert(0, entry(integration, doc.reference_doctype, doc.reference_docname, doc, 0))

	for integration in {item.integration for item in out}:
		group = [item for item in out if item.integration == integration]
		if not any(item.main for item in group):
			chosen = next((item for item in group if item.primary), group[0])
			chosen.main = 1
		elif sum(item.main for item in group) > 1:
			for item in [item for item in group if item.main][1:]:
				item.main = 0
	return out


def entry(integration, doctype, name, doc, main):
	return frappe._dict(
		integration=integration,
		doctype=doctype,
		name=name,
		main=main,
		primary=(doctype, name) == (doc.reference_doctype, doc.reference_docname),
	)


def get(contact, integration):
	return next((row for row in of(contact) if row.integration == integration and row.main), None)


def all_of(contact, integration):
	return [row for row in of(contact) if row.integration == integration]


def has(contact, doctype, name):
	return any((row.doctype, row.name) == (doctype, name) for row in of(contact))


def view(contact, integration):
	doc = frappe.get_doc(CONTACT, contact) if isinstance(contact, str) else contact
	row = get(doc, integration)
	out = copy.copy(doc)
	out.reference_doctype = row.doctype if row else None
	out.reference_docname = row.name if row else None
	return out


def attach(doc, doctype, name, main=False):
	integration = owner(doctype)
	if not integration:
		return
	current = of(doc)
	group = [row for row in current if row.integration == integration]
	existing = {(row.link_doctype, row.link_name) for row in doc.get("links") or []}
	for row in current:
		if (row.doctype, row.name) not in existing:
			doc.append(
				"links",
				{
					"integration": row.integration,
					"link_doctype": row.doctype,
					"link_name": row.name,
					"main": row.main,
				},
			)
	become_main = main or not group
	if (doctype, name) not in {(row.link_doctype, row.link_name) for row in doc.get("links")}:
		doc.append(
			"links", {"integration": integration, "link_doctype": doctype, "link_name": name, "main": 0}
		)
	if become_main:
		for row in doc.get("links"):
			if row.integration == integration:
				row.main = 1 if (row.link_doctype, row.link_name) == (doctype, name) else 0
	if not doc.reference_docname or (become_main and owner(doc.reference_doctype) == integration):
		doc.reference_doctype, doc.reference_docname = doctype, name


def normalize(contact):
	stored = {(row.link_doctype, row.link_name): row for row in stored_rows(contact)}
	for row in of(contact):
		saved = stored.get((row.doctype, row.name))
		if not saved:
			insert_row(contact, row.integration, row.doctype, row.name, row.main)
		elif cint(saved.main) != row.main:
			frappe.db.set_value(LINK, saved.name, "main", row.main, update_modified=False)


def insert_row(contact, integration, doctype, name, main):
	frappe.get_doc(
		{
			"doctype": LINK,
			"parent": contact,
			"parenttype": CONTACT,
			"parentfield": "links",
			"idx": frappe.db.count(LINK, {"parent": contact, "parenttype": CONTACT}) + 1,
			"integration": integration,
			"link_doctype": doctype,
			"link_name": name,
			"main": cint(main),
		}
	).insert(ignore_permissions=True)


def set_main(contact, integration, doctype, name):
	for row in stored_rows(contact):
		if row.integration == integration:
			flag = 1 if (row.link_doctype, row.link_name) == (doctype, name) else 0
			if cint(row.main) != flag:
				frappe.db.set_value(LINK, row.name, "main", flag, update_modified=False)


def set_primary(contact, doctype, name):
	frappe.db.set_value(
		CONTACT, contact, {"reference_doctype": doctype, "reference_docname": name}, update_modified=False
	)


def add(contact, doctype, name, main=False):
	integration = owner(doctype)
	if not integration:
		frappe.throw(
			frappe._("{0} records can't be linked to WhatsApp conversations.").format(frappe._(doctype))
		)

	normalize(contact)
	group = all_of(contact, integration)
	if not any((row.doctype, row.name) == (doctype, name) for row in group):
		insert_row(contact, integration, doctype, name, 0)
	become_main = main or not group
	if become_main:
		set_main(contact, integration, doctype, name)

	primary = frappe.db.get_value(CONTACT, contact, ["reference_doctype", "reference_docname"], as_dict=True)
	if not primary.reference_docname or (become_main and owner(primary.reference_doctype) == integration):
		set_primary(contact, doctype, name)
	return integration


def unlink(contact, doctype, name):
	integration = owner(doctype)
	normalize(contact)
	was_main = any(row.main and (row.doctype, row.name) == (doctype, name) for row in of(contact))
	frappe.db.delete(
		LINK, {"parent": contact, "parenttype": CONTACT, "link_doctype": doctype, "link_name": name}
	)
	primary = frappe.db.get_value(CONTACT, contact, ["reference_doctype", "reference_docname"], as_dict=True)
	cleared = (primary.reference_doctype, primary.reference_docname) == (doctype, name)
	if cleared:
		frappe.db.set_value(
			CONTACT, contact, {"reference_doctype": None, "reference_docname": None}, update_modified=False
		)
	rest = (
		[row for row in all_of(contact, integration) if (row.doctype, row.name) != (doctype, name)]
		if integration
		else []
	)
	if was_main and rest:
		set_main(contact, integration, rest[0].doctype, rest[0].name)
	if cleared:
		fallback = (get(contact, integration) if rest else None) or next(
			(row for row in of(contact) if row.main), None
		)
		if fallback:
			set_primary(contact, fallback.doctype, fallback.name)


def remove(contact, integration):
	for row in all_of(contact, integration):
		unlink(contact, row.doctype, row.name)
	frappe.db.delete(LINK, {"parent": contact, "parenttype": CONTACT, "integration": integration})


def make_main(contact, doctype, name):
	integration = owner(doctype)
	if not integration or not has(contact, doctype, name):
		frappe.throw(frappe._("{0} is not linked to this contact.").format(name))
	normalize(contact)
	set_main(contact, integration, doctype, name)
	primary = frappe.db.get_value(CONTACT, contact, ["reference_doctype", "reference_docname"], as_dict=True)
	if not primary.reference_docname or owner(primary.reference_doctype) == integration:
		set_primary(contact, doctype, name)


def make_primary(contact, integration):
	row = get(contact, integration)
	if row:
		set_primary(contact, row.doctype, row.name)


def contacts_for(doctype, name):
	table = frappe.qb.DocType(LINK)
	found = (
		frappe.qb.from_(table)
		.select(table.parent)
		.where((table.parenttype == CONTACT) & (table.link_doctype == doctype) & (table.link_name == name))
		.run(pluck=True)
	)
	primary = frappe.get_all(
		CONTACT, filters={"reference_doctype": doctype, "reference_docname": name}, pluck="name"
	)
	return list(dict.fromkeys(found + primary))


def with_doctype(table, doctype):
	link = frappe.qb.DocType(LINK)
	sub = (
		frappe.qb.from_(link)
		.select(link.parent)
		.where((link.parenttype == CONTACT) & (link.link_doctype == doctype))
	)
	return (table.reference_doctype == doctype) | table.name.isin(sub)


def by_contact(names):
	if not names:
		return {}
	out = {}
	for row in frappe.get_all(
		LINK,
		filters={"parent": ["in", list(names)], "parenttype": CONTACT},
		fields=["parent", "link_doctype"],
		order_by="idx asc",
	):
		out.setdefault(row.parent, []).append(row.link_doctype)
	return out


def pairs(contacts):
	out = {}
	names = [row.name for row in contacts]
	for index in range(0, len(names), 500):
		for row in frappe.get_all(
			LINK,
			filters={"parent": ["in", names[index : index + 500]], "parenttype": CONTACT},
			fields=["parent", "link_doctype", "link_name"],
			order_by="idx asc",
		):
			out.setdefault(row.parent, []).append((row.link_doctype, row.link_name))
	for row in contacts:
		if row.reference_doctype and row.reference_docname:
			out.setdefault(row.name, []).insert(0, (row.reference_doctype, row.reference_docname))
	return out


def describe(doctype, name):
	fields = TITLES.get(doctype)
	if not fields:
		return {}
	key = f"onechat:link-title:{doctype}:{name}"
	cached = frappe.cache().get_value(key)
	if cached is not None:
		return cached
	out = {}
	try:
		from onechat.integrations import connection

		wanted = [field for field in fields if field]
		row = connection.source_for(doctype).get_value(doctype, name, wanted) or {}
		out = {"title": row.get(fields[0]) or "", "status": row.get(fields[1]) if fields[1] else ""}
	except Exception:
		out = {}
	frappe.cache().set_value(key, out, expires_in_sec=TITLE_TTL)
	return out


def public(contact):
	specs = {spec["name"]: spec for spec in integrations.specs()}
	rows = sorted(of(contact), key=lambda row: (row.integration, -row.main))
	out = []
	for row in rows:
		spec = specs.get(row.integration) or {}
		meta = next((item for item in spec.get("link_doctypes", []) if item["doctype"] == row.doctype), {})
		info = describe(row.doctype, row.name)
		out.append(
			{
				"integration": row.integration,
				"label": spec.get("label") or row.integration,
				"logo": spec.get("logo"),
				"icon": meta.get("icon") or spec.get("icon"),
				"theme": meta.get("theme") or "gray",
				"type": row.doctype,
				"doctype": row.doctype,
				"name": row.name,
				"title": info.get("title") or "",
				"status": info.get("status") or "",
				"main": bool(row.main),
				"primary": row.primary,
			}
		)
	return out
