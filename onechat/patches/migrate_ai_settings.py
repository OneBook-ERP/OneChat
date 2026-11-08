import frappe
from frappe.utils.password import get_decrypted_password, remove_encrypted_password

SETTINGS = "OneChat Settings"
PROVIDER = "OneChat AI Provider"
OLD_KEYS = {
	"Claude": "assistant_anthropic_key",
	"OpenAI": "assistant_openai_key",
	"Other": "assistant_other_key",
}
OLD_FIELDS = (
	"assistant_provider",
	"assistant_claude_model",
	"assistant_openai_model",
	"assistant_other_name",
	"assistant_other_url",
	"assistant_other_model",
	*OLD_KEYS.values(),
)
DEFAULT_MODELS = {"Claude": "claude-opus-5-5", "OpenAI": "gpt-6.1-sol"}


def old_value(field):
	rows = frappe.db.sql("select value from `tabSingles` where doctype=%s and field=%s", (SETTINGS, field))
	return ((rows[0][0] if rows else "") or "").strip()


def old_key(field):
	return (get_decrypted_password(SETTINGS, SETTINGS, field, raise_exception=False) or "").strip()


def install(preset_id, key, api_base, model_id, name=""):
	from onechat.assistant import presets

	provider, added = presets.install(presets.find(preset_id), key, api_base, [model_id], name)
	return provider, added[0]


def planned(old, keys):
	out = {}
	if keys["Claude"]:
		out["Claude"] = ("anthropic", None, old["assistant_claude_model"] or DEFAULT_MODELS["Claude"], "")
	if keys["OpenAI"]:
		out["OpenAI"] = ("openai", None, old["assistant_openai_model"] or DEFAULT_MODELS["OpenAI"], "")
	if old["assistant_other_url"] and old["assistant_other_model"]:
		name = old["assistant_other_name"] or "Custom"
		out["Other"] = ("custom", old["assistant_other_url"], old["assistant_other_model"], name)
	return out


def execute():
	old = {field: old_value(field) for field in OLD_FIELDS}
	keys = {provider: old_key(field) for provider, field in OLD_KEYS.items()}
	for doctype in ("onechat_ai_provider", "onechat_ai_model", "onechat_settings"):
		frappe.reload_doc("onechat", "doctype", doctype)

	models = {}
	for label, (preset_id, api_base, model_id, name) in planned(old, keys).items():
		provider, models[label] = install(preset_id, keys[label], api_base, model_id, name)
		stored = frappe.get_doc(PROVIDER, provider).resolved_key() or ""
		if stored != keys[label]:
			frappe.throw(f"OneChat could not copy the {label} API key. Nothing was removed.")

	current = models.get(old["assistant_provider"] or "Claude") or next(iter(models.values()), None)
	if current and not frappe.db.get_single_value(SETTINGS, "assistant_model"):
		frappe.db.set_single_value(SETTINGS, "assistant_model", current)

	for field in OLD_KEYS.values():
		remove_encrypted_password(SETTINGS, SETTINGS, field)
	frappe.db.sql(
		"delete from `tabSingles` where doctype=%s and field in %s",
		(SETTINGS, tuple(OLD_FIELDS)),
	)
