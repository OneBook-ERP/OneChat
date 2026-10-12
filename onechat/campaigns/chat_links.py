import io
import json
import random
import re
from urllib.parse import quote

import frappe
from frappe import _
from frappe.integrations.utils import make_get_request
from frappe.query_builder.functions import IfNull
from frappe.utils import add_days, cint, get_datetime, get_url, getdate, now_datetime

from onechat.campaigns.broadcasts import ensure_admin
from onechat.inbox.conversations import CONTACT, MESSAGE, digits, publish

LINK = "OneChat Chat Link"
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE = re.compile(r"^[A-Z0-9]{4,12}$")
REF = re.compile(r"\[ref:([A-Za-z0-9]{4,12})\]")
SYMBOLS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
MARK = "\u2063"
DIGITS = "\u200b\u200c\u200d\u2060"
HIDDEN = re.compile(f"{MARK}([{DIGITS}]+){MARK}")
BOTS = re.compile(
	r"bot|crawl|spider|preview|facebookexternalhit|whatsapp|telegram|slack|discord|curl|python|wget", re.I
)
MIN_MATCH = 12


def hidden(code):
	marks = []
	for char in (code or "").upper():
		index = SYMBOLS.index(char)
		marks.append(DIGITS[index // 16] + DIGITS[(index // 4) % 4] + DIGITS[index % 4])
	return f"{MARK}{''.join(marks)}{MARK}"


def reveal(text):
	match = HIDDEN.search(text or "")
	if not match or len(match.group(1)) % 3:
		return None
	marks = match.group(1)
	chars = []
	for start in range(0, len(marks), 3):
		index = (
			DIGITS.index(marks[start]) * 16
			+ DIGITS.index(marks[start + 1]) * 4
			+ DIGITS.index(marks[start + 2])
		)
		if index >= len(SYMBOLS):
			return None
		chars.append(SYMBOLS[index])
	return "".join(chars)


def short_url(code):
	return get_url(f"/c/{code}") if code else None


def plain(text):
	return " ".join((text or "").lower().split())


def tracked_links():
	cached = getattr(frappe.local, "onechat_tracked_links", None)
	if cached is None:
		cached = frappe.get_all(
			LINK, filters={"track": 1}, fields=["name", "prefilled_message", "meta_ad_ids"]
		)
		frappe.local.onechat_tracked_links = cached
	return cached


def by_message(text):
	said = plain(text)
	if len(said) < MIN_MATCH:
		return None
	for link in tracked_links():
		expected = plain(link.prefilled_message)
		if len(expected) >= MIN_MATCH and said.startswith(expected):
			return link.name
	return None


def by_ad(referral):
	source = str((referral or {}).get("source_id") or "")
	if not source:
		return None
	for link in tracked_links():
		ids = re.split(r"[\s,]+", link.meta_ad_ids or "")
		if source in ids:
			return link.name
	return None


def detect(text):
	code = reveal(text)
	clean = HIDDEN.sub("", text or "").strip() if code else text
	if not code:
		legacy = REF.search(text or "")
		code = legacy.group(1).upper() if legacy else None
	link = frappe.db.get_value(LINK, {"ref_code": code}, "name") if code else None
	return clean, link or by_message(clean)


def new_code():
	for attempt in range(20):
		code = "OC" + "".join(random.choices(ALPHABET, k=4))
		if not frappe.db.exists(LINK, {"ref_code": code}):
			return code

	return "OC" + frappe.generate_hash(length=8).upper()


def tagged(message, code, track):
	text = (message or "").strip()
	if cint(track) and code:
		text = f"{text}{hidden(code)}"

	return text


def build_url(number, message=None, code=None, track=1):
	number = digits(number)
	if not number:
		return None

	text = tagged(message, code, track)
	return f"https://wa.me/{number}" + (f"?text={quote(text)}" if text else "")


def build_instagram_url(username, code=None, track=1):
	if not username:
		return None
	return f"https://ig.me/m/{username}" + (f"?ref={quote(code)}" if code and cint(track) else "")


def lookup_number(account):
	if not account:
		return None

	known = frappe.db.get_value(
		LINK, {"whatsapp_account": account, "display_number": ["is", "set"]}, "display_number"
	)
	if known:
		return known

	try:
		doc = frappe.get_doc("OneChat Account", account)
		response = make_get_request(
			f"{doc.url}/{doc.version}/{doc.phone_id}",
			headers={"authorization": f"Bearer {doc.get_password('token')}"},
			params={"fields": "display_phone_number"},
		)
		return (response or {}).get("display_phone_number")
	except Exception:
		frappe.log_error(title="OneChat chat link number")
		return None


@frappe.whitelist()
def account_number(whatsapp_account: str):
	ensure_admin()
	return lookup_number(whatsapp_account)


@frappe.whitelist()
def qr(name: str | None = None, url: str | None = None):
	ensure_admin()
	if name:
		url = frappe.db.get_value(LINK, name, "link_url")

	if not url or not (url.startswith("https://wa.me/") or url.startswith(get_url("/c/"))):
		frappe.throw(_("Add the WhatsApp number to build the link first."))

	return {"url": url, "svg": svg(url)}


def svg(url):
	try:
		import pyqrcode
	except ImportError:
		return None

	buffer = io.BytesIO()
	pyqrcode.create(url, error="M").svg(
		buffer, scale=8, module_color="#000000", background="#ffffff", xmldecl=False, quiet_zone=4
	)
	return buffer.getvalue().decode()


@frappe.whitelist()
def stats(name: str, days: int | str = 30):
	ensure_admin()
	from onechat.workspace.session import require_read

	require_read(LINK, name)
	days = min(max(cint(days) or 30, 1), 90)
	link = frappe.db.get_value(
		LINK,
		name,
		["ref_code", "conversations", "last_conversation_at", "clicks", "last_click_at"],
		as_dict=True,
	)
	if not link:
		frappe.throw(_("Link not found"), frappe.DoesNotExistError)

	today = getdate(now_datetime())
	start = get_datetime(add_days(today, 1 - days))
	counts = {}
	matches = [[MESSAGE, "chat_link", "=", name]]
	if link.ref_code:
		matches.append([MESSAGE, "message", "like", f"%[ref:{link.ref_code}]%"])
	for row in frappe.get_all(
		MESSAGE,
		filters=[[MESSAGE, "type", "=", "Incoming"], [MESSAGE, "creation", ">=", start]],
		or_filters=matches,
		fields=["creation"],
		limit_page_length=5000,
	):
		day = getdate(row.creation)
		counts[day] = counts.get(day, 0) + 1

	series = [counts.get(add_days(today, offset - days + 1), 0) for offset in range(days)]

	return {
		"conversations": cint(link.conversations),
		"last_conversation_at": link.last_conversation_at,
		"clicks": cint(link.clicks),
		"last_click_at": link.last_click_at,
		"recent": sum(series),
		"days": days,
		"series": series,
	}


def referral_of(doc):
	raw = doc.get("referral")
	if not raw:
		return None
	try:
		return json.loads(raw) if isinstance(raw, str) else raw
	except ValueError:
		return None


def on_message(doc, method=None):
	if doc.type != "Incoming":
		return

	referral = referral_of(doc)
	name = doc.get("chat_link") or by_ad(referral)
	if not name and doc.content_type == "text":
		legacy = REF.search(doc.message or "")
		name = frappe.db.get_value(LINK, {"ref_code": legacy.group(1).upper()}, "name") if legacy else None

	contact = doc.get("whatsapp_contact") or frappe.db.get_value(MESSAGE, doc.name, "whatsapp_contact")
	if not name:
		if referral and contact:
			remember_source(contact, ad_source(referral))
		return

	try:
		link = frappe.db.get_value(LINK, name, ["name", "label", "title"], as_dict=True)
		if not link:
			return
		if doc.get("chat_link") != link.name:
			frappe.db.set_value(MESSAGE, doc.name, "chat_link", link.name, update_modified=False)

		table = frappe.qb.DocType(LINK)
		(
			frappe.qb.update(table)
			.set(table.conversations, IfNull(table.conversations, 0) + 1)
			.set(table.last_conversation_at, now_datetime())
			.where(table.name == link.name)
			.run()
		)

		if contact:
			remember_source(contact, _("Link: {0}").format(link.title))
		if link.label and contact:
			apply_label(contact, link.label)
	except Exception:
		frappe.log_error(title="OneChat chat link")


def ad_source(referral):
	kind = _("Ad") if referral.get("source_type") == "ad" else _("Post")
	title = referral.get("headline") or referral.get("source_url") or referral.get("source_id") or ""
	return f"{kind}: {title}".strip()[:140]


def remember_source(contact, source):
	if not source or not frappe.get_meta(CONTACT).has_field("source"):
		return
	if not frappe.db.get_value(CONTACT, contact, "source"):
		frappe.db.set_value(CONTACT, contact, "source", source[:140], update_modified=False)


def click(code):
	code = (code or "").strip().upper()
	link = (
		frappe.db.get_value(LINK, {"ref_code": code}, ["name", "link_url"], as_dict=True)
		if CODE.match(code)
		else None
	)
	if not link or not link.link_url:
		raise frappe.DoesNotExistError
	agent = frappe.get_request_header("User-Agent") or ""
	if agent and not BOTS.search(agent):
		table = frappe.qb.DocType(LINK)
		(
			frappe.qb.update(table)
			.set(table.clicks, IfNull(table.clicks, 0) + 1)
			.set(table.last_click_at, now_datetime())
			.where(table.name == link.name)
			.run()
		)
		frappe.db.commit()
	return link.link_url


def apply_label(contact, label):
	if not frappe.get_meta(CONTACT).has_field("labels") or not frappe.db.exists("OneChat Label", label):
		return

	doc = frappe.get_doc(CONTACT, contact)
	if any(row.label == label for row in doc.get("labels") or []):
		return

	doc.append("labels", {"label": label})
	doc.save(ignore_permissions=True)
	publish(contact)
