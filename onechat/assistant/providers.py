import json

import frappe
from frappe import _

CLAUDE = "Claude"
OPENAI = "OpenAI"
OTHER = "Other"
CLAUDE_MODEL = "claude-opus-5"
OPENAI_MODEL = "gpt-5"
MAX_TOKENS = 16000
MIN_TOKENS = 1024
TOKEN_CEILING = 64000


def token_limit(value):
	try:
		number = int(value or 0)
	except (TypeError, ValueError):
		number = 0
	return min(max(number or MAX_TOKENS, MIN_TOKENS), TOKEN_CEILING)


class ProviderError(Exception):
	pass


class Turn:
	def __init__(self, text="", calls=None, refused=False):
		self.text = text
		self.calls = calls or []
		self.refused = refused


class Claude:
	def __init__(self, key, system, tools, model=None, max_tokens=MAX_TOKENS):
		try:
			import anthropic
		except ImportError as error:
			raise ProviderError(
				_("Install the anthropic Python package on the server to use Claude.")
			) from error
		self.anthropic = anthropic
		self.client = anthropic.Anthropic(api_key=key)
		self.system = system
		self.model = model or CLAUDE_MODEL
		self.max_tokens = max_tokens
		self.tools = [
			{"name": tool["name"], "description": tool["description"], "input_schema": tool["schema"]}
			for tool in tools
		]

	def ask(self, messages, text):
		messages.append({"role": "user", "content": text})

	def step(self, messages):
		try:
			params = {"tools": self.tools} if self.tools else {}
			with self.client.beta.messages.stream(
				model=self.model,
				max_tokens=self.max_tokens,
				system=self.system,
				messages=messages,
				cache_control={"type": "ephemeral"},
				output_config={"effort": "medium"},
				betas=["server-side-fallback-2026-07-01"],
				fallbacks="default",
				**params,
			) as stream:
				response = stream.get_final_message()
		except self.anthropic.AuthenticationError as error:
			raise ProviderError(
				_("The Claude API key was rejected. Check it in Settings → Assistant.")
			) from error
		except self.anthropic.RateLimitError as error:
			raise ProviderError(_("Claude is busy right now. Try again in a minute.")) from error
		except self.anthropic.APIStatusError as error:
			raise ProviderError(_("Claude returned an error: {0}").format(error.message)) from error
		except self.anthropic.APIConnectionError as error:
			raise ProviderError(
				_("Could not reach Claude. Check the server's internet connection.")
			) from error

		messages.append({"role": "assistant", "content": [block.to_dict() for block in response.content]})
		if response.stop_reason == "refusal":
			return Turn(refused=True)
		calls = [
			{"id": block.id, "name": block.name, "input": block.input or {}}
			for block in response.content
			if block.type == "tool_use"
		]
		text = "".join(block.text for block in response.content if block.type == "text")
		return Turn(text, calls)

	def results(self, messages, rows):
		messages.append(
			{
				"role": "user",
				"content": [
					{
						"type": "tool_result",
						"tool_use_id": row["id"],
						"content": row["text"],
						"is_error": row["error"],
					}
					for row in rows
				],
			}
		)


class OpenAIProvider:
	def __init__(self, key, system, tools, model=None, max_tokens=MAX_TOKENS, base_url=None, label=OPENAI):
		try:
			import openai
		except ImportError as error:
			raise ProviderError(
				_("Install the openai Python package on the server to use {0}.").format(label)
			) from error
		self.openai = openai
		self.client = (
			openai.OpenAI(api_key=key, base_url=base_url) if base_url else openai.OpenAI(api_key=key)
		)
		self.label = label
		self.compatible = bool(base_url)
		self.system = system
		self.model = model or OPENAI_MODEL
		self.max_tokens = max_tokens
		self.tools = [
			{
				"type": "function",
				"function": {
					"name": tool["name"],
					"description": tool["description"],
					"parameters": tool["schema"],
				},
			}
			for tool in tools
		]

	def ask(self, messages, text):
		messages.append({"role": "user", "content": text})

	def step(self, messages):
		params = {
			"model": self.model,
			"messages": [{"role": "system", "content": self.system}, *messages],
		}
		params["max_tokens" if self.compatible else "max_completion_tokens"] = self.max_tokens
		if self.tools:
			params["tools"] = self.tools
		try:
			response = self.client.chat.completions.create(**params)
		except self.openai.AuthenticationError as error:
			raise ProviderError(
				_("The {0} API key was rejected. Check it in Settings → Assistant.").format(self.label)
			) from error
		except self.openai.RateLimitError as error:
			raise ProviderError(
				_("{0} is busy right now. Try again in a minute.").format(self.label)
			) from error
		except self.openai.APIStatusError as error:
			raise ProviderError(_("{0} returned an error: {1}").format(self.label, error.message)) from error
		except self.openai.APIConnectionError as error:
			raise ProviderError(
				_("Could not reach {0}. Check the address and the server's internet connection.").format(
					self.label
				)
			) from error

		message = response.choices[0].message
		messages.append(message.model_dump(exclude_none=True))
		if getattr(message, "refusal", None):
			return Turn(refused=True)
		calls = []
		for call in message.tool_calls or []:
			try:
				arguments = json.loads(call.function.arguments or "{}")
			except ValueError:
				arguments = {}
			calls.append({"id": call.id, "name": call.function.name, "input": arguments})
		return Turn(message.content or "", calls)

	def results(self, messages, rows):
		for row in rows:
			messages.append({"role": "tool", "tool_call_id": row["id"], "content": row["text"]})


def build(settings, system, tools):
	provider = settings.get("assistant_provider") or CLAUDE
	limit = token_limit(settings.get("assistant_max_tokens"))
	if provider == OTHER:
		label = (settings.get("assistant_other_name") or "").strip() or _("the AI provider")
		url = (settings.get("assistant_other_url") or "").strip()
		model = (settings.get("assistant_other_model") or "").strip()
		key = settings.get_password("assistant_other_key", raise_exception=False)
		if not (url and model and key):
			raise ProviderError(
				_("Add the address, API key and model for {0} in Settings → Assistant.").format(label)
			)
		return OpenAIProvider(key, system, tools, model, limit, base_url=url, label=label)
	if provider == OPENAI:
		key = settings.get_password("assistant_openai_key", raise_exception=False)
		if not key:
			raise ProviderError(_("Add an OpenAI API key in Settings → Assistant."))
		return OpenAIProvider(
			key, system, tools, (settings.get("assistant_openai_model") or "").strip() or None, limit
		)
	key = settings.get_password("assistant_anthropic_key", raise_exception=False)
	if not key:
		raise ProviderError(_("Add a Claude API key in Settings → Assistant."))
	return Claude(key, system, tools, (settings.get("assistant_claude_model") or "").strip() or None, limit)
