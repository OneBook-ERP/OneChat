from urllib.parse import urlparse

import frappe
import requests
from packaging.version import InvalidVersion, Version

import onechat
from onechat.workspace.session import is_admin, require_app_user

DEFAULT_SOURCE = "https://raw.githubusercontent.com/OneBook-ERP/OneChat/announcements/announcements.json"
CACHE_KEY = "onechat:announcements:feed"
FEED_SECONDS = 900
FAILED_SECONDS = 120
TIMEOUT = 5
LIMIT = 20
GITHUB_HOSTS = ("raw.githubusercontent.com", "api.github.com")


def source():
	return (frappe.conf.get("onechat_announcement_source", DEFAULT_SOURCE) or "").strip()


def headers(url):
	token = (frappe.conf.get("onechat_announcement_token") or "").strip()
	if not token or urlparse(url).hostname not in GITHUB_HOSTS:
		return {}
	return {"Authorization": f"token {token}"}


def normalize(data):
	if isinstance(data, list):
		data = {"announcements": data}
	if not isinstance(data, dict):
		data = {}
	items = data.get("announcements") or data.get("message") or []
	updates = data.get("updates") or []
	items = items if isinstance(items, list) else []
	updates = updates if isinstance(updates, list) else []
	return {
		"announcements": [
			item for item in items if isinstance(item, dict) and item.get("id") and item.get("enabled", True)
		][:LIMIT],
		"updates": [row for row in updates if isinstance(row, dict) and row.get("version")],
	}


def remote_feed():
	cache = frappe.cache()
	data = cache.get_value(CACHE_KEY)
	if data is not None:
		return normalize(data)
	url = source()
	if not url:
		return normalize(None)
	try:
		response = requests.get(url, headers=headers(url), timeout=TIMEOUT)
		response.raise_for_status()
		data = normalize(response.json())
	except (requests.RequestException, ValueError):
		cache.set_value(CACHE_KEY, normalize(None), expires_in_sec=FAILED_SECONDS)
		return normalize(None)
	cache.set_value(CACHE_KEY, data, expires_in_sec=FEED_SECONDS)
	return data


@frappe.whitelist()
def announcements():
	require_app_user()
	admin = is_admin()
	data = remote_feed()
	items = [
		item
		for item in data["announcements"]
		if (admin or item.get("audience") != "Admins only") and for_this_install(item)
	]
	update = update_notice(data["updates"]) if admin else None
	return [update, *items] if update else items


def parsed(value):
	try:
		return Version(str(value).strip().lstrip("v")) if value else None
	except InvalidVersion:
		return None


def app_version():
	return parsed(onechat.__version__)


def frappe_major():
	return str(frappe.__version__).split(".")[0]


def listed(value):
	if isinstance(value, str):
		value = value.split(",")
	return [str(part).strip() for part in value or [] if str(part).strip()]


def for_this_install(item):
	branches = listed(item.get("versions"))
	if branches and frappe_major() not in branches:
		return False
	current = app_version()
	lowest, highest = parsed(item.get("min_version")), parsed(item.get("max_version"))
	if current and lowest and current < lowest:
		return False
	if current and highest and current > highest:
		return False
	return True


def update_notice(updates):
	current = app_version()
	if not current:
		return None
	release = next(
		(
			row
			for row in updates
			if not listed(row.get("versions")) or frappe_major() in listed(row.get("versions"))
		),
		None,
	)
	latest = parsed(release.get("version")) if release else None
	if not latest or latest <= current:
		return None
	return {
		"id": f"update-{latest}",
		"type": "card",
		"theme": "info",
		"label": "Update available",
		"title": release.get("title") or f"OneChat {latest} is available",
		"body": release.get("body")
		or f"You're on {current}. Ask your administrator or Frappe Cloud to update.",
		"action": {"label": release.get("label") or "What's new", "url": release["url"]}
		if release.get("url")
		else None,
		"audience": "Admins only",
	}
