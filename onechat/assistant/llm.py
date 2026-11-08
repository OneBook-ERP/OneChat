import os
import sys
import threading
import time

import frappe
from frappe import _

PROVIDER = "OneChat AI Provider"
MODEL = "OneChat AI Model"
TIMEOUT = 120
RETRIES = 1
RETRY_DELAY = 1
NO_KEY = "not-needed"
CACHE = {"type": "ephemeral"}
KEYLESS = ("openai",)
TRANSIENT = frozenset(
	{"APIConnectionError", "InternalServerError", "ServiceUnavailableError", "Timeout", "APITimeoutError"}
)
QUOTA_WORDS = ("quota", "per day", "billing", "credit")


class ModelError(frappe.ValidationError):
	pass


def fixable_messages():
	return {
		"AuthenticationError": _("The AI provider rejected the API key. Change it in Settings → Assistant."),
		"PermissionDeniedError": _(
			"The AI provider refused this request for your account. Check the key in Settings → Assistant."
		),
		"NotFoundError": _("The selected model isn't available from its provider. Pick another one."),
		"ContextWindowExceededError": _(
			"This conversation is too long for the model. Clear the chat and ask again."
		),
		"ContentPolicyViolationError": _("The AI provider declined this request under its content policy."),
		"RateLimitError": _("The AI provider is busy right now. Try again in a minute."),
		"ServiceUnavailableError": _("The AI provider can't serve this model right now. Try again shortly."),
		"Timeout": _("The AI provider took too long to answer. Try again."),
		"APIConnectionError": _(
			"Could not reach the AI provider. Check the provider address and the internet."
		),
	}


def named(error, names):
	return any(cls.__name__ in names for cls in type(error).__mro__)


def out_of_quota(error):
	text = str(error).lower()
	return named(error, {"RateLimitError"}) and any(word in text for word in QUOTA_WORDS)


def user_facing_error(error):
	if getattr(error, "status_code", None) == 402:
		return _("The AI provider account is out of credit or has a billing problem.")
	if out_of_quota(error):
		return _(
			"The AI provider's quota for this key is used up, for example a free tier's daily limit. "
			"Turn on billing for the key or pick another model in Settings → Assistant."
		)
	messages = fixable_messages()
	for cls in type(error).__mro__:
		if cls.__name__ in messages:
			return messages[cls.__name__]
	return _("Something went wrong talking to the AI provider. Try again.")


def resolve(model_name):
	if not model_name or not frappe.db.exists(MODEL, model_name):
		raise ModelError(_("Pick an assistant model in Settings → Assistant."))
	model = frappe.get_cached_doc(MODEL, model_name)
	provider = frappe.get_cached_doc(PROVIDER, model.provider)
	if not (model.enabled and provider.enabled):
		raise ModelError(
			_("{0} is switched off. Pick another model in Settings → Assistant.").format(model.label)
		)
	key = provider.resolved_key()
	if not key and not (provider.api_base and provider.litellm_provider in KEYLESS):
		raise ModelError(_("Add the API key for {0} in Settings → Assistant.").format(provider.name))
	return frappe._dict(
		name=model.name,
		label=model.label,
		model=f"{provider.litellm_provider}/{model.model_id}",
		api_key=key or NO_KEY,
		api_base=provider.api_base,
	)


def ready(model_name):
	try:
		resolve(model_name)
	except ModelError:
		return False
	return True


def is_claude(model):
	return "claude" in model


def with_cache(model, messages):
	if not (is_claude(model) and messages and messages[0].get("role") == "system"):
		return messages
	system = messages[0]
	if not isinstance(system.get("content"), str):
		return messages
	block = {"type": "text", "text": system["content"], "cache_control": CACHE}
	return [{**system, "content": [block]}, *messages[1:]]


def routing(target):
	out = {"api_base": target.api_base} if target.api_base else {}
	if target.model.startswith("openrouter/") and is_claude(target.model):
		out["extra_body"] = {"provider": {"order": ["anthropic"], "allow_fallbacks": False}}
	return out


def library():
	os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
	import litellm

	return litellm


def warm():
	if "litellm" in sys.modules or getattr(warm, "started", False):
		return
	warm.started = True
	threading.Thread(target=library, daemon=True, name="onechat-litellm-warm").start()


def call(target, messages, tools, max_tokens):
	return library().completion(
		model=target.model,
		messages=with_cache(target.model, messages),
		max_tokens=max_tokens,
		api_key=target.api_key,
		timeout=TIMEOUT,
		num_retries=0,
		drop_params=True,
		**({"tools": tools} if tools else {}),
		**routing(target),
	)


def complete(target, messages, tools, max_tokens):
	for attempt in range(RETRIES + 1):
		try:
			return call(target, messages, tools, max_tokens)
		except Exception as error:
			if attempt == RETRIES or not named(error, TRANSIENT):
				raise
			time.sleep(RETRY_DELAY)
