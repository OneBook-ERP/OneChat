import re

import frappe
from frappe import _
from frappe.utils import cint

from onechat.api_types import JSON
from onechat.assistant import llm, presets
from onechat.workspace.session import require_admin

SETTINGS = "OneChat Settings"


def provider_rows():
	models = frappe.get_all(
		llm.MODEL, fields=["name", "provider", "model_id", "label", "enabled"], order_by="creation asc"
	)
	out = []
	for row in frappe.get_all(
		llm.PROVIDER,
		fields=["name", "preset", "litellm_provider", "api_base", "enabled"],
		order_by="creation asc",
	):
		out.append(
			{
				**row,
				"has_key": bool(frappe.get_doc(llm.PROVIDER, row.name).resolved_key()),
				"models": [model for model in models if model.provider == row.name],
			}
		)
	return out


def state():
	return {"providers": provider_rows(), "presets": [presets.public(preset) for preset in presets.PRESETS]}


def preset_of(preset_id):
	found = presets.find(preset_id)
	if not found:
		frappe.throw(_("Unknown provider {0}.").format(preset_id))
	return found


def model_ids(models):
	if isinstance(models, str):
		text = models.strip()
		try:
			parsed = frappe.parse_json(text)
		except Exception:
			parsed = None
		models = parsed if isinstance(parsed, list) else re.split(r"[,\n]", text)
	return list(dict.fromkeys(str(model).strip() for model in models or [] if str(model).strip()))


def default_model(preset):
	return next((model_id for model_id, _label, _note, recommended in preset["models"] if recommended), "")


@frappe.whitelist(methods=["POST"])
def verify_key(preset: str, api_key: str = "", api_base: str = "", model_id: str = "", name: str = ""):
	require_admin()
	found = preset_of(preset)
	model_id = (model_id or "").strip() or default_model(found)
	if not model_id:
		return {"success": False, "severity": "error", "message": _("Enter a model ID to test with.")}
	api_key = (api_key or "").strip() or presets.stored_key(name or found["name"]) or ""
	return presets.verify(found, api_key, api_base, model_id)


def use_if_unset(model_name):
	settings = frappe.get_doc(SETTINGS)
	if settings.get("assistant_model") or not model_name:
		return
	settings.assistant_model = model_name
	settings.save(ignore_permissions=True)


@frappe.whitelist(methods=["POST"])
def add_provider(preset: str, api_key: str = "", api_base: str = "", models: JSON = None, name: str = ""):
	require_admin()
	found = preset_of(preset)
	chosen = model_ids(models)
	if not chosen:
		frappe.throw(_("Pick at least one model."))
	if found.get("custom") and not (api_base or "").strip():
		frappe.throw(_("Add the address of the OpenAI-compatible server."))
	_provider, added = presets.install(found, api_key, api_base, chosen, name)
	use_if_unset(added[0] if added else None)
	return state()


@frappe.whitelist(methods=["POST"])
def set_model_enabled(name: str, enabled: bool | int | str = 1):
	require_admin()
	frappe.db.set_value(llm.MODEL, name, "enabled", cint(enabled))
	frappe.clear_document_cache(llm.MODEL, name)
	return state()


@frappe.whitelist(methods=["POST"])
def update_key(name: str, api_key: str):
	require_admin()
	if not (api_key or "").strip():
		frappe.throw(_("Paste the new API key."))
	doc = frappe.get_doc(llm.PROVIDER, name)
	doc.api_key = api_key.strip()
	doc.save(ignore_permissions=True)
	return state()


@frappe.whitelist(methods=["POST"])
def remove_provider(name: str):
	require_admin()
	settings = frappe.get_doc(SETTINGS)
	current = settings.get("assistant_model")
	if current and frappe.db.get_value(llm.MODEL, current, "provider") == name:
		settings.assistant_model = None
		settings.save(ignore_permissions=True)
	for model in frappe.get_all(llm.MODEL, filters={"provider": name}, pluck="name"):
		frappe.delete_doc(llm.MODEL, model, ignore_permissions=True)
	frappe.delete_doc(llm.PROVIDER, name, ignore_permissions=True)
	return state()
