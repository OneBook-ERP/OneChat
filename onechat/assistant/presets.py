import frappe
from frappe import _

PROVIDER = "OneChat AI Provider"
MODEL = "OneChat AI Model"
NO_KEY = "not-needed"
TEST_PROMPT = "Reply with OK"

PRESETS = [
	{
		"id": "anthropic",
		"name": "Anthropic",
		"tagline": "Claude, direct",
		"blurb": "Straight to Anthropic with your own account. Claude is strong at reading records and writing replies.",
		"litellm_provider": "anthropic",
		"api_base": None,
		"key_url": "https://console.anthropic.com/settings/keys",
		"key_prefix": "sk-ant-",
		"key_steps": [
			"Sign in to the Anthropic Console",
			"Open Settings, then API keys",
			"Create a key and copy it",
		],
		"models": [
			("claude-opus-5-5", "Claude Opus 5.5", "Most capable, best for the assistant", True),
			("claude-sonnet-5-5", "Claude Sonnet 5.5", "Faster and cheaper", False),
			("claude-haiku-5-5", "Claude Haiku 5.5", "Fastest and cheapest, for simple replies", False),
		],
	},
	{
		"id": "openai",
		"name": "OpenAI",
		"tagline": "GPT, direct",
		"blurb": "Straight to OpenAI with your own account.",
		"litellm_provider": "openai",
		"api_base": None,
		"key_url": "https://platform.openai.com/api-keys",
		"key_prefix": "sk-",
		"key_steps": [
			"Sign in at platform.openai.com",
			"Open API keys and create a secret key",
			"Copy it before closing the dialog",
		],
		"models": [
			("gpt-6.1-sol", "GPT-6.1 Sol", "Latest, best value", True),
			("gpt-6-astra", "GPT-6 Astra", "Top tier, much pricier", False),
		],
	},
	{
		"id": "openrouter",
		"name": "OpenRouter",
		"tagline": "One key, every major model",
		"blurb": "Claude, GPT, Gemini and many more behind a single key. Switch models without a new account.",
		"litellm_provider": "openrouter",
		"api_base": None,
		"key_url": "https://openrouter.ai/keys",
		"key_prefix": "sk-or-",
		"key_steps": ["Sign in at openrouter.ai", "Open Keys and create a new key", "Add a little credit"],
		"models": [
			("anthropic/claude-opus-5.5", "Claude Opus 5.5", "Most capable", True),
			("anthropic/claude-sonnet-5.5", "Claude Sonnet 5.5", "Faster and cheaper", False),
			("openai/gpt-6.1-sol", "GPT-6.1 Sol", "OpenAI's latest", False),
			("google/gemini-3.8-flash", "Gemini 3.8 Flash", "Google's latest, fast", False),
		],
	},
	{
		"id": "google",
		"name": "Google Gemini",
		"tagline": "Gemini, direct",
		"blurb": "Straight to Google AI Studio. A generous free tier to try things out.",
		"litellm_provider": "gemini",
		"api_base": None,
		"key_url": "https://aistudio.google.com/apikey",
		"key_prefix": "",
		"key_steps": [
			"Open Google AI Studio",
			"Click Get API key",
			"Create a key in a new or existing project",
		],
		"models": [
			("gemini-3.8-flash", "Gemini 3.8 Flash", "Latest, fast", True),
			("gemini-3.1-pro-preview", "Gemini 3.1 Pro", "Strongest Gemini", False),
		],
	},
	{
		"id": "custom",
		"name": "",
		"tagline": "Any OpenAI-compatible address",
		"blurb": "Your own gateway: an internal proxy, a hosted endpoint not listed here, or Ollama, LM Studio or vLLM.",
		"litellm_provider": "openai",
		"api_base": "",
		"custom": True,
		"key_url": "",
		"key_prefix": "",
		"key_steps": [],
		"models": [],
	},
]


def find(preset_id):
	return next((preset for preset in PRESETS if preset["id"] == preset_id), None)


def stored_key(name):
	if not name or not frappe.db.exists(PROVIDER, name):
		return None
	return frappe.get_doc(PROVIDER, name).resolved_key()


def public(preset):
	return {
		"id": preset["id"],
		"name": preset["name"],
		"tagline": preset["tagline"],
		"blurb": preset["blurb"],
		"key_url": preset["key_url"],
		"key_prefix": preset["key_prefix"],
		"key_steps": preset["key_steps"],
		"custom": bool(preset.get("custom")),
		"configured": bool(preset["name"] and frappe.db.exists(PROVIDER, preset["name"])),
		"has_key": bool(stored_key(preset["name"])),
		"models": [
			{"model_id": model_id, "label": label, "note": note, "recommended": recommended}
			for model_id, label, note, recommended in preset["models"]
		],
	}


def provider_name(preset, name):
	value = (name or preset["name"] or "").strip()
	if not value:
		frappe.throw(_("Give this provider a name."))
	return value


def save_provider(preset, name, api_key, api_base):
	values = {
		"provider_name": name,
		"preset": preset["id"],
		"litellm_provider": preset["litellm_provider"],
		"api_base": (api_base or preset["api_base"] or "").strip() or None,
		"enabled": 1,
	}
	if api_key:
		values["api_key"] = api_key.strip()
	if frappe.db.exists(PROVIDER, name):
		doc = frappe.get_doc(PROVIDER, name)
		doc.update(values)
		doc.save(ignore_permissions=True)
		return doc
	return frappe.get_doc({"doctype": PROVIDER, **values}).insert(ignore_permissions=True)


def add_model(provider, model_id, label, enabled=True):
	from onechat.onechat.doctype.onechat_ai_model.onechat_ai_model import full_name

	name = full_name(provider, model_id)
	if frappe.db.exists(MODEL, name):
		if enabled:
			frappe.db.set_value(MODEL, name, "enabled", 1)
		return name
	frappe.get_doc(
		{
			"doctype": MODEL,
			"provider": provider,
			"model_id": model_id,
			"label": label,
			"enabled": int(enabled),
		}
	).insert(ignore_permissions=True)
	return name


def install(preset, api_key, api_base, model_ids, name=""):
	name = provider_name(preset, name)
	doc = save_provider(preset, name, api_key, api_base)
	known = {model_id: label for model_id, label, _note, _rec in preset["models"]}
	added = [add_model(doc.name, model_id, known.get(model_id, model_id)) for model_id in model_ids]
	for model_id, label in known.items():
		if model_id not in model_ids:
			add_model(doc.name, model_id, label, enabled=False)
	return doc.name, added


def verify(preset, api_key, api_base, model_id):
	from onechat.assistant import llm

	base = (api_base or preset["api_base"] or "").strip() or None
	try:
		llm.library().completion(
			model=f"{preset['litellm_provider']}/{model_id}",
			messages=[{"role": "user", "content": TEST_PROMPT}],
			max_tokens=16,
			api_key=api_key or NO_KEY,
			timeout=llm.TIMEOUT,
			**({"api_base": base} if base else {}),
		)
		return {"success": True, "severity": "ok", "message": _("Connected")}
	except Exception as error:
		message, severity = readable_error(str(error))
		return {"success": False, "severity": severity, "message": message}


def readable_error(raw):
	low = raw.lower()
	if "authentication" in low or ("invalid" in low and "key" in low) or "401" in low:
		return _(
			"That key was rejected. Check you copied all of it and that it hasn't been revoked."
		), "error"
	if "credit" in low or "quota" in low or "billing" in low or "429" in low:
		return _("The key is valid, but the account has no credit or is rate limited right now."), "warn"
	if "not found" in low or "404" in low or "does not exist" in low:
		return _("The key is valid, but that model isn't available on this account."), "warn"
	if "connection" in low or "timeout" in low or "refused" in low:
		return _("Couldn't reach the server. Check the address is right and that it's running."), "error"
	return raw[:300], "error"
