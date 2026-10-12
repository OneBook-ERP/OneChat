import hashlib
import io
import json
import re

import frappe
from frappe import _

from onechat.api_types import JSON
from onechat.workspace.session import require_admin, require_app_user

SETTINGS = "OneChat Settings"
STATIC = "/assets/onechat/frontend/icons"
SIZES = (64, 180, 192, 512)
COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
DEFAULTS = {
	"app_name": "OneChat",
	"app_short_name": "OneChat",
	"app_icon": None,
	"app_theme_color": "#1f8a5b",
	"app_install_button": 1,
}


def values():
	meta = frappe.get_meta(SETTINGS)
	out = dict(DEFAULTS)
	for key in DEFAULTS:
		if meta.has_field(key):
			value = frappe.db.get_single_value(SETTINGS, key)
			if value not in (None, ""):
				out[key] = value
	if not COLOR.match(out["app_theme_color"] or ""):
		out["app_theme_color"] = DEFAULTS["app_theme_color"]
	return out


def version(current):
	return hashlib.md5(f"{current.get('app_icon')}{current['app_theme_color']}".encode()).hexdigest()[:8]


def icons(current):
	if not current.get("app_icon"):
		return [
			{"src": f"{STATIC}/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
			{"src": f"{STATIC}/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
			{
				"src": f"{STATIC}/maskable-512.png",
				"sizes": "512x512",
				"type": "image/png",
				"purpose": "maskable",
			},
		]
	stamp = version(current)
	base = "/api/method/onechat.pwa.icon"
	return [
		{"src": f"{base}?size=192&v={stamp}", "sizes": "192x192", "type": "image/png", "purpose": "any"},
		{"src": f"{base}?size=512&v={stamp}", "sizes": "512x512", "type": "image/png", "purpose": "any"},
		{
			"src": f"{base}?size=512&maskable=1&v={stamp}",
			"sizes": "512x512",
			"type": "image/png",
			"purpose": "maskable",
		},
	]


def apple_icon(current=None):
	current = current or values()
	if not current.get("app_icon"):
		return f"{STATIC}/apple-touch-icon.png"
	return f"/api/method/onechat.pwa.icon?size=180&v={version(current)}"


def favicon(current=None):
	current = current or values()
	if not current.get("app_icon"):
		return "/assets/onechat/frontend/onechat-mark.svg"
	return f"/api/method/onechat.pwa.icon?size=64&v={version(current)}"


@frappe.whitelist(allow_guest=True)
def manifest():
	current = values()
	body = {
		"id": "/onechat",
		"name": current["app_name"],
		"short_name": current["app_short_name"] or current["app_name"],
		"description": _("Meta business inbox and automation"),
		"start_url": "/onechat",
		"scope": "/onechat",
		"display": "standalone",
		"background_color": "#ffffff",
		"theme_color": current["app_theme_color"],
		"icons": icons(current),
	}
	frappe.response.update(
		{
			"type": "binary",
			"filename": "manifest.json",
			"filecontent": json.dumps(body).encode(),
			"display_content_as": "inline",
		}
	)


def square(image, size, pad=0.0, background=None):
	from PIL import Image

	image = image.convert("RGBA")
	side = min(image.size)
	left = (image.width - side) // 2
	top = (image.height - side) // 2
	image = image.crop((left, top, left + side, top + side))
	inner = max(1, round(size * (1 - pad * 2)))
	image = image.resize((inner, inner), Image.LANCZOS)
	canvas = Image.new("RGBA", (size, size), background or (0, 0, 0, 0))
	offset = (size - inner) // 2
	canvas.alpha_composite(image, (offset, offset))
	return canvas


def render(file_url, size, maskable, color):
	from PIL import Image

	content = frappe.get_doc("File", {"file_url": file_url}).get_content()
	image = Image.open(io.BytesIO(content))
	background = (*tuple(int(color[index : index + 2], 16) for index in (1, 3, 5)), 255)
	out = square(image, size, 0.1 if maskable else 0.0, background if maskable or size == 180 else None)
	buffer = io.BytesIO()
	out.save(buffer, format="PNG", optimize=True)
	return buffer.getvalue()


@frappe.whitelist(allow_guest=True)
def icon(size: int | str = 192, maskable: int | str = 0, v: str | None = None):
	current = values()
	size = int(size) if str(size).isdigit() and int(size) in SIZES else 192
	maskable = 1 if str(maskable) in ("1", "true") else 0
	if not current.get("app_icon"):
		name = (
			"maskable-512"
			if maskable
			else ("apple-touch-icon" if size == 180 else f"icon-{512 if size == 512 else 192}")
		)
		frappe.local.flags.redirect_location = f"{STATIC}/{name}.png"
		raise frappe.Redirect

	key = f"onechat:pwa:icon:{current['app_icon']}:{size}:{maskable}:{current['app_theme_color']}"
	content = frappe.cache().get_value(key)
	if not content:
		content = render(current["app_icon"], size, maskable, current["app_theme_color"])
		frappe.cache().set_value(key, content, expires_in_sec=86400)
	frappe.response.update(
		{
			"type": "binary",
			"filename": f"icon-{size}.png",
			"filecontent": content,
			"display_content_as": "inline",
		}
	)


@frappe.whitelist()
def settings():
	require_app_user()
	current = values()
	return {
		**current,
		"icons": icons(current),
		"apple_icon": apple_icon(current),
		"favicon": favicon(current),
	}


@frappe.whitelist()
def save_settings(
	app_name: str | None = None,
	app_short_name: str | None = None,
	app_icon: str | None = None,
	app_theme_color: str | None = None,
	app_install_button: JSON = None,
):
	require_admin()
	if not frappe.get_meta(SETTINGS).has_field("app_name"):
		frappe.throw(_("Run bench migrate to finish setting up the app settings."))
	name = (app_name or "").strip() or DEFAULTS["app_name"]
	short = (app_short_name or "").strip() or name[:12]
	if len(short) > 12:
		frappe.throw(_("Keep the short name to 12 characters so it fits under the icon."))
	color = (app_theme_color or "").strip() or DEFAULTS["app_theme_color"]
	if not COLOR.match(color):
		frappe.throw(_("Pick a colour like #1f8a5b."))
	if app_icon:
		from PIL import Image

		try:
			image = Image.open(io.BytesIO(frappe.get_doc("File", {"file_url": app_icon}).get_content()))
		except Exception:
			frappe.throw(_("That file is not an image OneChat can read. Upload a PNG or JPG."))
		if min(image.size) < 192:
			frappe.throw(
				_("The icon should be at least 512 × 512 pixels. This one is {0} × {1}.").format(*image.size)
			)
	doc = frappe.get_single(SETTINGS)
	doc.update(
		{
			"app_name": name,
			"app_short_name": short,
			"app_icon": app_icon or None,
			"app_theme_color": color,
			"app_install_button": 1 if frappe.parse_json(app_install_button) else 0,
		}
	)
	doc.save()
	return settings()
