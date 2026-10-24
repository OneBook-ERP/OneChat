import json
from concurrent.futures import ThreadPoolExecutor

import frappe
import requests
from frappe import _
from frappe.utils import cint, flt, get_url

from onechat.api_types import JSON
from onechat.whatsapp.accounts import admin_only, token

ACCOUNT = "OneChat Account"
TIMEOUT = 60
PRODUCT_FIELDS = (
	"id,retailer_id,name,description,price,currency,availability,image_url,url,brand,review_status,visibility"
)
PAGE = 50


class MetaError(frappe.ValidationError):
	def __init__(self, message, code=None, detail=None):
		super().__init__(message)
		self.code = code
		self.detail = detail


def meta(account, method, path, params=None, data=None, payload=None, quiet=False):
	response = requests.request(
		method,
		f"{account.url}/{account.version}/{path}",
		params=params,
		data=data,
		json=payload,
		headers={"Authorization": f"Bearer {token(account)}"},
		timeout=TIMEOUT,
	)
	try:
		body = response.json()
	except ValueError:
		body = {}
	if not response.ok:
		error = body.get("error") or {}
		message = error.get("error_user_msg") or error.get("message") or response.text[:300]
		if error.get("code") in (10, 200) or "permission" in message.lower():
			message = _(
				"{0} The access token needs the catalog_management and business_management permissions."
			).format(message)
		if quiet:
			raise MetaError(
				message,
				error.get("code"),
				error.get("error_user_msg") or error.get("message") or response.text[:300],
			)
		frappe.throw(message, title=_("Meta"))
	return body


def load(name):
	admin_only()
	account = frappe.get_doc(ACCOUNT, name)
	if not account.business_id or not token(account):
		frappe.throw(_("Add the WhatsApp Business Account ID and access token to this number first."))
	return account


def owner(account):
	info = (
		meta(account, "GET", account.business_id, {"fields": "owner_business_info"}).get(
			"owner_business_info"
		)
		or {}
	)
	if not info.get("id"):
		frappe.throw(_("Meta did not return the business that owns this WhatsApp account."))
	return info


def save_catalog_id(account, catalog_id):
	frappe.db.set_value(ACCOUNT, account.name, "catalog_id", catalog_id or None)


def attempt(doc, method, path, params=None):
	try:
		return meta(doc, method, path, params, quiet=True), None
	except MetaError as error:
		return {}, error


def fetch(base, auth, path, params=None):
	response = requests.get(f"{base}/{path}", params=params, headers=auth, timeout=TIMEOUT)
	try:
		body = response.json()
	except ValueError:
		body = {}
	if response.ok:
		return body, None
	error = body.get("error") or {}
	detail = error.get("error_user_msg") or error.get("message") or response.text[:300]
	return {}, MetaError(detail, error.get("code"), detail)


def gather(doc, calls):
	base = f"{doc.url}/{doc.version}"
	auth = {"Authorization": f"Bearer {token(doc)}"}
	with ThreadPoolExecutor(max_workers=len(calls)) as pool:
		futures = {key: pool.submit(fetch, base, auth, *call) for key, call in calls.items()}
		return {key: future.result() for key, future in futures.items()}


def problem(error):
	if not error:
		return None
	if error.code == 190:
		kind = "token"
	elif error.code in (10, 200) or "permission" in (error.detail or "").lower():
		kind = "permission"
	else:
		kind = "error"
	return {"kind": kind, "detail": error.detail}


@frappe.whitelist()
def state(account: str, with_products: bool | int | str | None = None):
	doc = load(account)
	calls = {
		"catalogs": (f"{doc.business_id}/product_catalogs", {"fields": "id,name,product_count"}),
		"info": (doc.business_id, {"fields": "owner_business_info"}),
	}
	if doc.phone_id:
		calls["commerce"] = (f"{doc.phone_id}/whatsapp_commerce_settings",)
	if cint(with_products) and doc.catalog_id:
		calls["products"] = (f"{doc.catalog_id}/products", page_params())
	results = gather(doc, calls)
	body, blocked = results["catalogs"]
	connected = body.get("data") or []
	current = connected[0] if connected else None
	business, owned, limited, commerce, first = {}, [], None, {}, None
	if not blocked:
		info, limited = results["info"]
		business = info.get("owner_business_info") or {}
		if business.get("id") and not current:
			listing, limited = attempt(
				doc,
				"GET",
				f"{business['id']}/owned_product_catalogs",
				{"fields": "id,name,product_count,vertical", "limit": 100},
			)
			owned = listing.get("data") or []
		if "commerce" in results:
			commerce = (results["commerce"][0].get("data") or [{}])[0]
		if "products" in results and current and current.get("id") == doc.catalog_id:
			page, failed = results["products"]
			first = None if failed else page_of(page)
		if (current or {}).get("id") != doc.catalog_id:
			save_catalog_id(doc, (current or {}).get("id"))
	return {
		"products": first,
		"business": business,
		"blocked": problem(blocked),
		"limited": problem(limited),
		"catalog": current,
		"owned": [row for row in owned if row.get("vertical") in (None, "commerce")],
		"cart": bool(commerce.get("is_cart_enabled")),
		"visible": bool(commerce.get("is_catalog_visible")),
	}


@frappe.whitelist(methods=["POST"])
def create(account: str, name: str):
	doc = load(account)
	name = (name or "").strip()
	if not name:
		frappe.throw(_("Give the catalog a name."))
	business = owner(doc)
	catalog = meta(
		doc, "POST", f"{business['id']}/owned_product_catalogs", data={"name": name, "vertical": "commerce"}
	)
	meta(doc, "POST", f"{doc.business_id}/product_catalogs", data={"catalog_id": catalog["id"]})
	save_catalog_id(doc, catalog["id"])
	return state(account)


@frappe.whitelist(methods=["POST"])
def connect(account: str, catalog_id: str):
	doc = load(account)
	for row in meta(doc, "GET", f"{doc.business_id}/product_catalogs").get("data") or []:
		if row.get("id") != catalog_id:
			meta(doc, "DELETE", f"{doc.business_id}/product_catalogs", params={"catalog_id": row["id"]})
	meta(doc, "POST", f"{doc.business_id}/product_catalogs", data={"catalog_id": catalog_id})
	save_catalog_id(doc, catalog_id)
	return state(account)


@frappe.whitelist(methods=["POST"])
def disconnect(account: str, catalog_id: str):
	doc = load(account)
	meta(doc, "DELETE", f"{doc.business_id}/product_catalogs", params={"catalog_id": catalog_id})
	save_catalog_id(doc, None)
	return state(account)


@frappe.whitelist(methods=["POST"])
def rename(account: str, catalog_id: str, name: str):
	doc = load(account)
	if not (name or "").strip():
		frappe.throw(_("Give the catalog a name."))
	meta(doc, "POST", catalog_id, data={"name": name.strip()})
	return state(account)


@frappe.whitelist(methods=["POST"])
def delete(account: str, catalog_id: str):
	doc = load(account)
	if catalog_id == doc.catalog_id:
		meta(doc, "DELETE", f"{doc.business_id}/product_catalogs", params={"catalog_id": catalog_id})
		save_catalog_id(doc, None)
	meta(doc, "DELETE", catalog_id)
	return state(account)


@frappe.whitelist(methods=["POST"])
def set_commerce(account: str, cart: bool | int | str | None = None, visible: bool | int | str | None = None):
	doc = load(account)
	if not doc.phone_id:
		frappe.throw(_("Add the phone number ID to this number first."))
	params = {}
	if cart is not None:
		params["is_cart_enabled"] = "true" if cint(cart) else "false"
	if visible is not None:
		params["is_catalog_visible"] = "true" if cint(visible) else "false"
	meta(doc, "POST", f"{doc.phone_id}/whatsapp_commerce_settings", params=params)
	return state(account)


def catalog_of(doc):
	if not doc.catalog_id:
		frappe.throw(_("Create or connect a catalog first."))
	return doc.catalog_id


@frappe.whitelist()
def products(account: str, search: str | None = None, after: str | None = None):
	return catalog_page(load(account), search, after)


def page_params(search=None, after=None):
	params = {"fields": PRODUCT_FIELDS, "limit": PAGE}
	if after:
		params["after"] = after
	text = (search or "").strip()
	if text:
		params["filter"] = json.dumps(
			{"or": [{"name": {"i_contains": text}}, {"retailer_id": {"i_contains": text}}]}
		)
	return params


def catalog_page(doc, search=None, after=None):
	return page_of(meta(doc, "GET", f"{catalog_of(doc)}/products", page_params(search, after)))


def page_of(body):
	cursors = (body.get("paging") or {}).get("cursors") or {}
	return {
		"rows": body.get("data") or [],
		"after": cursors.get("after") if (body.get("paging") or {}).get("next") else None,
	}


def item_data(values):
	retailer_id = (values.get("retailer_id") or "").strip()
	title = (values.get("name") or "").strip()
	currency = (values.get("currency") or "").strip().upper()
	if not retailer_id or not title:
		frappe.throw(_("Enter a product ID and a name."))
	if flt(values.get("price")) <= 0 or len(currency) != 3:
		frappe.throw(_("Enter a price and a three-letter currency, for example 1499 INR."))
	if not (values.get("image_url") or "").strip():
		frappe.throw(_("Add an image. Meta does not accept products without one."))
	data = {
		"id": retailer_id,
		"title": title[:150],
		"description": ((values.get("description") or "").strip() or title)[:9999],
		"availability": values.get("availability") or "in stock",
		"condition": "new",
		"price": f"{flt(values.get('price')):.2f} {currency}",
		"image_link": get_url(values["image_url"].strip())
		if values["image_url"].startswith("/")
		else values["image_url"].strip(),
		"link": (values.get("url") or "").strip() or get_url(),
	}
	if (values.get("brand") or "").strip():
		data["brand"] = values["brand"].strip()[:100]
	return data


def batch(doc, requests_list):
	body = meta(
		doc,
		"POST",
		f"{catalog_of(doc)}/items_batch",
		payload={"item_type": "PRODUCT_ITEM", "allow_upsert": True, "requests": requests_list},
	)
	return body.get("handles") or []


@frappe.whitelist(methods=["POST"])
def save_product(account: str, values: JSON):
	doc = load(account)
	values = frappe.parse_json(values) or {}
	batch(doc, [{"method": "UPDATE", "data": item_data(values)}])
	return _("Saved. Meta usually shows the change within a few minutes.")


@frappe.whitelist(methods=["POST"])
def delete_products(account: str, retailer_ids: JSON):
	doc = load(account)
	ids = [value for value in frappe.parse_json(retailer_ids) or [] if value]
	if not ids:
		frappe.throw(_("Pick the products to delete."))
	batch(doc, [{"method": "DELETE", "data": {"id": value}} for value in ids])
	return _("{0} products are being removed from the catalog.").format(len(ids))


@frappe.whitelist()
def product_sets(account: str):
	doc = load(account)
	path = f"{catalog_of(doc)}/product_sets"
	try:
		rows = (
			meta(
				doc,
				"GET",
				path,
				{"fields": "id,name,product_count,filter,products.limit(4){image_url}", "limit": 100},
				quiet=True,
			).get("data")
			or []
		)
	except MetaError:
		rows = (
			meta(doc, "GET", path, {"fields": "id,name,product_count,filter", "limit": 100}).get("data") or []
		)
	for row in rows:
		row["images"] = [
			item.get("image_url")
			for item in (row.pop("products", None) or {}).get("data") or []
			if item.get("image_url")
		]
	return rows


@frappe.whitelist(methods=["POST"])
def save_product_set(account: str, name: str, retailer_ids: JSON, set_id: str | None = None):
	doc = load(account)
	ids = [value for value in frappe.parse_json(retailer_ids) or [] if value]
	if not (name or "").strip():
		frappe.throw(_("Give the collection a name."))
	if not ids:
		frappe.throw(_("Pick at least one product for the collection."))
	data = {"name": name.strip(), "filter": json.dumps({"retailer_id": {"is_any": ids}})}
	if set_id:
		meta(doc, "POST", set_id, data=data)
	else:
		meta(doc, "POST", f"{catalog_of(doc)}/product_sets", data=data)
	return product_sets(account)


@frappe.whitelist(methods=["POST"])
def delete_product_set(account: str, set_id: str):
	doc = load(account)
	meta(doc, "DELETE", set_id)
	return product_sets(account)
