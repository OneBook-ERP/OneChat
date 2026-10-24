import json
import re
from urllib.parse import quote

import frappe
import requests
from frappe import _
from frappe.utils import cint, get_url, now_datetime, strip_html
from frappe.utils.password import get_decrypted_password

CONNECTION = "OneChat Connection"
THIS_SITE = "This site"
ANOTHER_SITE = "Another site"
OAUTH = "OAuth"
API_KEY = "API key"
TIMEOUT = 20
META_TTL = 3600
FIELDS = [
	"mode",
	"url",
	"auth_method",
	"client_id",
	"token_expires_at",
	"oauth_user",
	"api_key",
	"connected",
	"status",
	"checked_at",
	"webhooks",
	"last_event_at",
	"last_event",
	"role_status",
]

APPS = {
	"erpnext": {"app": "erpnext", "label": "ERPNext"},
	"crm": {"app": "crm", "label": "Frappe CRM"},
}


class RemoteError(frappe.ValidationError):
	def __init__(self, message, status=None, transient=False):
		super().__init__(message)
		self.status = status
		self.transient = transient


class Site:
	def __init__(self, key):
		if key not in APPS:
			frappe.throw(_("Unknown integration {0}.").format(key))
		self.key = key
		self.app = APPS[key]["app"]
		self.label = APPS[key]["label"]

	def row(self):
		cache = getattr(frappe.local, "onechat_connections", None)
		if cache is None:
			cache = frappe.local.onechat_connections = {}
		if self.key not in cache:
			if not frappe.db.table_exists(CONNECTION):
				return frappe._dict()
			cache[self.key] = (
				frappe.db.get_value(CONNECTION, self.key, FIELDS, as_dict=True) or frappe._dict()
			)
		return frappe._dict(cache[self.key])

	def forget(self):
		cache = getattr(frappe.local, "onechat_connections", None)
		if cache:
			cache.pop(self.key, None)
		from onechat import integrations

		integrations.forget()

	def mode(self):
		return self.row().get("mode") or THIS_SITE

	def is_remote(self):
		return self.mode() == ANOTHER_SITE

	def base_url(self):
		return (self.row().get("url") or "").strip().rstrip("/")

	def uses_oauth(self):
		return self.row().get("auth_method") == OAUTH

	def authorization(self, force=False):
		if self.uses_oauth():
			from onechat.integrations import oauth

			return f"Bearer {oauth.access_token(self, force=force)}"
		key, secret = self.credentials()
		return f"token {key}:{secret}"

	def credentials(self):
		key = self.row().get("api_key")
		secret = (
			get_decrypted_password(CONNECTION, self.key, "api_secret", raise_exception=False) if key else None
		)
		return key, secret

	def installed_here(self):
		return self.app in frappe.get_installed_apps()

	def ready(self):
		if self.is_remote():
			if self.uses_oauth():
				values = self.row()
				return bool(self.base_url() and values.get("client_id") and values.get("token_expires_at"))
			key, secret = self.credentials()
			return bool(self.base_url() and key and secret)
		return self.installed_here()

	def client(self):
		return Remote(self)

	def source(self):
		return Remote(self) if self.is_remote() else Local()

	def url(self, path):
		return f"{self.base_url()}{path}" if self.is_remote() else path

	def desk_url(self, doctype, name=None):
		path = f"/app/{frappe.scrub(doctype).replace('_', '-')}"
		if name:
			path += f"/{quote(str(name), safe='')}"
		return self.url(path)

	def doc(self):
		if frappe.db.exists(CONNECTION, self.key):
			return frappe.get_doc(CONNECTION, self.key)
		return frappe.get_doc({"doctype": CONNECTION, "integration": self.key})

	def update(self, values):
		doc = self.doc()
		doc.update(values)
		doc.flags.ignore_permissions = True
		doc.save()
		self.forget()
		return doc

	def record_status(self, text, ok):
		self.update({"connected": 1 if ok else 0, "status": text, "checked_at": now_datetime()})

	def test(self):
		client = self.client()
		user = client.call("frappe.auth.get_logged_user")
		apps = client.call("frappe.utils.change_log.get_versions") or {}
		if self.app not in apps:
			raise RemoteError(
				_("Connected as {0}, but {1} is not installed on that site.").format(user, self.label)
			)
		return {"user": user, "version": (apps.get(self.app) or {}).get("version")}

	def clear_cache(self):
		frappe.cache().delete_value(f"onechat:remote:{self.key}:doctypes")
		frappe.cache().delete_keys(f"onechat:remote:{self.key}:meta:")


def site(key):
	return Site(key)


def remote_sites():
	return [row for row in (Site(key) for key in APPS) if row.is_remote() and row.ready()]


def local_doctype(doctype):
	return bool(doctype) and bool(frappe.db.exists("DocType", doctype))


def owner_of(doctype):
	if not doctype or local_doctype(doctype):
		return None
	for row in remote_sites():
		try:
			if doctype in remote_doctypes(row):
				return row
		except RemoteError:
			continue
	return None


def source_for(doctype):
	owner = owner_of(doctype)
	return Remote(owner) if owner else Local()


def remote_doctypes(row):
	key = f"onechat:remote:{row.key}:doctypes"
	cached = frappe.cache().get_value(key)
	if cached is not None:
		return cached

	names = [
		item.name
		for item in Remote(row).get_list("DocType", fields=["name"], filters={"istable": 0}, limit=0)
	]
	frappe.cache().set_value(key, names, expires_in_sec=META_TTL)
	return names


FUNCTION_FIELD = re.compile(r"^\s*(\w+)\s*\((.*)\)\s+as\s+(\w+)\s*$", re.I)
STRING_FUNCTIONS = "not allowed as strings"


def modern_fields(fields):
	out = []
	for field in fields or []:
		match = FUNCTION_FIELD.match(field) if isinstance(field, str) else None
		out.append(
			{match.group(1).upper(): match.group(2).strip() or "*", "as": match.group(3)} if match else field
		)
	return out


def modern_here():
	return cint(str(frappe.__version__).split(".")[0]) >= 16


def local_fields(fields):
	return modern_fields(fields) if modern_here() else fields


class Local:
	remote = False

	def get_list(
		self, doctype, fields=None, filters=None, order_by=None, limit=20, group_by=None, or_filters=None
	):
		return frappe.get_list(
			doctype,
			fields=local_fields(fields or ["name"]),
			filters=filters,
			or_filters=or_filters,
			order_by=order_by,
			group_by=group_by,
			limit_page_length=limit,
		)

	def get_all(
		self, doctype, fields=None, filters=None, order_by=None, limit=0, or_filters=None, group_by=None
	):
		return frappe.get_all(
			doctype,
			fields=local_fields(fields or ["name"]),
			filters=filters,
			or_filters=or_filters,
			order_by=order_by,
			group_by=group_by,
			limit_page_length=limit,
		)

	def get_value(self, doctype, filters, fields):
		return frappe.db.get_value(doctype, filters, fields, as_dict=isinstance(fields, list | tuple))

	def single_value(self, doctype, field):
		return frappe.db.get_single_value(doctype, field)

	def get_doc(self, doctype, name):
		return frappe._dict(frappe.get_doc(doctype, name).as_dict(no_default_fields=False))

	def exists(self, doctype, filters):
		return bool(frappe.db.exists(doctype, filters))

	def has_doctype(self, doctype):
		return local_doctype(doctype)

	def insert(self, doc, ignore_permissions=False):
		return frappe._dict(frappe.get_doc(doc).insert(ignore_permissions=ignore_permissions).as_dict())

	def update(self, doctype, name, values, ignore_permissions=False):
		doc = frappe.get_doc(doctype, name)
		doc.update(values)
		doc.save(ignore_permissions=ignore_permissions)
		return frappe._dict(doc.as_dict())

	def call(self, method, **kwargs):
		result = frappe.get_attr(method)(**kwargs)
		return frappe._dict(result.as_dict()) if hasattr(result, "as_dict") else result

	def absolute(self, path):
		return path if not path or path.startswith("http") else get_url(path)


class Remote:
	remote = True

	def __init__(self, row):
		self.site = row
		self.url = row.base_url()
		if not (self.url and row.ready()):
			frappe.throw(_("Finish the {0} connection in Settings → Integrations first.").format(row.label))

	def request(self, method, path, **kwargs):
		label = self.site.label
		response = self.send(method, path, self.site.authorization(), **kwargs)
		if response.status_code == 401 and self.site.uses_oauth():
			response = self.send(method, path, self.site.authorization(force=True), **kwargs)

		try:
			body = response.json()
		except ValueError:
			body = {}

		if response.status_code in (401, 403):
			hint = (
				_("{0} refused the sign-in. Sign in again, or check the user's roles.")
				if self.site.uses_oauth()
				else _("{0} refused the API key. Check the key, the secret and the user's roles.")
			)
			raise RemoteError(error_text(body) or hint.format(label), status=response.status_code)
		if not response.ok:
			raise RemoteError(
				error_text(body) or _("{0} returned an error ({1}).").format(label, response.status_code),
				status=response.status_code,
				transient=response.status_code in (429, 502, 503, 504),
			)

		return body

	def send(self, method, path, authorization, **kwargs):
		try:
			return requests.request(
				method,
				f"{self.url}{path}",
				headers={"Authorization": authorization, "Accept": "application/json"},
				timeout=TIMEOUT,
				**kwargs,
			)
		except requests.RequestException as error:
			raise RemoteError(
				_("Could not reach {0} at {1}: {2}").format(self.site.label, self.url, str(error)),
				transient=True,
			) from error

	def call(self, method, **kwargs):
		return as_dicts(self.request("POST", f"/api/method/{method}", json=kwargs).get("message"))

	def modern_key(self):
		return f"onechat:remote:{self.site.key}:modern-fields"

	def get_list(
		self, doctype, fields=None, filters=None, order_by=None, limit=20, group_by=None, or_filters=None
	):
		fields = fields or ["name"]
		payload = {"doctype": doctype, "limit_page_length": limit}
		for key, value in (
			("filters", filters),
			("or_filters", or_filters),
			("order_by", order_by),
			("group_by", group_by),
		):
			if value:
				payload[key] = value
		modern = modern_fields(fields)
		if modern == fields:
			return self.call("frappe.client.get_list", fields=fields, **payload) or []
		if frappe.cache().get_value(self.modern_key()):
			return self.call("frappe.client.get_list", fields=modern, **payload) or []
		try:
			return self.call("frappe.client.get_list", fields=fields, **payload) or []
		except RemoteError as error:
			if STRING_FUNCTIONS not in str(error):
				raise
			frappe.cache().set_value(self.modern_key(), 1, expires_in_sec=86400)
			return self.call("frappe.client.get_list", fields=modern, **payload) or []

	def get_all(
		self, doctype, fields=None, filters=None, order_by=None, limit=0, or_filters=None, group_by=None
	):
		return self.get_list(
			doctype, fields, filters, order_by, limit, group_by=group_by, or_filters=or_filters
		)

	def get_value(self, doctype, filters, fields):
		many = isinstance(fields, list | tuple)
		result = self.call(
			"frappe.client.get_value",
			doctype=doctype,
			fieldname=list(fields) if many else fields,
			filters=filters if isinstance(filters, dict) else {"name": filters},
			as_dict=1,
		)
		if not result:
			return None
		return result if many else result.get(fields)

	def single_value(self, doctype, field):
		return self.call("frappe.client.get_single_value", doctype=doctype, field=field)

	def get_doc(self, doctype, name):
		return as_dicts(
			self.request("GET", f"/api/resource/{quote(doctype)}/{quote(str(name), safe='')}").get("data")
			or {}
		)

	def exists(self, doctype, filters):
		return bool(self.get_value(doctype, filters, "name"))

	def has_doctype(self, doctype):
		return doctype in remote_doctypes(self.site)

	def insert(self, doc, ignore_permissions=False):
		return self.call("frappe.client.insert", doc=doc)

	def update(self, doctype, name, values, ignore_permissions=False):
		return self.call("frappe.client.set_value", doctype=doctype, name=name, fieldname=values)

	def submit(self, doc):
		return self.call("frappe.client.submit", doc=doc)

	def absolute(self, path):
		return path if not path or path.startswith("http") else f"{self.url}{path}"

	def meta_fields(self, doctype):
		key = f"onechat:remote:{self.site.key}:meta:{doctype}"
		cached = frappe.cache().get_value(key)
		if cached is not None:
			return cached

		body = self.request(
			"GET", "/api/method/frappe.desk.form.load.getdoctype", params={"doctype": doctype}
		)
		docs = body.get("docs") or []
		meta = next((row for row in docs if row.get("name") == doctype), docs[0] if docs else {})
		fields = [
			{
				"fieldname": row.get("fieldname"),
				"label": row.get("label") or row.get("fieldname"),
				"fieldtype": row.get("fieldtype"),
				"options": row.get("options"),
				"reqd": row.get("reqd"),
				"default": row.get("default"),
				"read_only": row.get("read_only"),
				"hidden": row.get("hidden"),
				"in_standard_filter": row.get("in_standard_filter"),
				"in_list_view": row.get("in_list_view"),
			}
			for row in meta.get("fields") or []
			if row.get("fieldname")
		]
		frappe.cache().set_value(key, fields, expires_in_sec=META_TTL)
		return fields

	def search(self, doctype, txt="", filters=None, page_length=20):
		return (
			self.call(
				"frappe.desk.search.search_link",
				doctype=doctype,
				txt=txt or "",
				filters=filters or None,
				page_length=page_length,
			)
			or []
		)


def as_dicts(value):
	if isinstance(value, list):
		return [as_dicts(row) for row in value]
	if isinstance(value, dict):
		return frappe._dict({key: as_dicts(item) for key, item in value.items()})
	return value


def error_text(body):
	messages = body.get("_server_messages")
	if messages:
		try:
			rows = [json.loads(row) for row in json.loads(messages)]
			text = " ".join(
				strip_html(row.get("message") if isinstance(row, dict) else str(row)) for row in rows
			)
			if text.strip():
				return text.strip()
		except (TypeError, ValueError):
			pass
	if body.get("exception"):
		return str(body["exception"]).split(":", 1)[-1].strip()
	if isinstance(body.get("message"), str):
		return body["message"]
	return None
