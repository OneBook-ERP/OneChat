import json

import frappe

from onechat.assistant import llm

MAX_TOKENS = 16000
MIN_TOKENS = 1024
TOKEN_CEILING = 64000
REFUSED = "content_filter"


def token_limit(value):
	try:
		number = int(value or 0)
	except (TypeError, ValueError):
		number = 0
	return min(max(number or MAX_TOKENS, MIN_TOKENS), TOKEN_CEILING)


class ProviderError(Exception):
	pass


class Turn:
	def __init__(self, text="", calls=None, refused=False, usage=None):
		self.text = text
		self.calls = calls or []
		self.refused = refused
		self.usage = usage or {}


def arguments_of(raw):
	if isinstance(raw, dict):
		return raw
	try:
		value = json.loads(raw or "{}")
	except ValueError:
		try:
			from json_repair import repair_json

			value = repair_json(raw or "", return_objects=True)
		except Exception:
			value = {}
	return value if isinstance(value, dict) else {}


def usage_of(response):
	usage = getattr(response, "usage", None)
	if not usage:
		return {}
	return {
		"input": getattr(usage, "prompt_tokens", 0) or 0,
		"output": getattr(usage, "completion_tokens", 0) or 0,
	}


class Provider:
	def __init__(self, target, system, tools, max_tokens=MAX_TOKENS):
		self.target = target
		self.system = system
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
		history = [{"role": "system", "content": self.system}, *messages]
		try:
			response = llm.complete(self.target, history, self.tools, self.max_tokens)
		except Exception as error:
			frappe.log_error(title=f"OneChat assistant: {self.target.label}")
			raise ProviderError(llm.user_facing_error(error)) from error

		choice = response.choices[0]
		if choice.finish_reason == REFUSED:
			return Turn(refused=True, usage=usage_of(response))
		message = choice.message
		messages.append(message.model_dump(exclude_none=True))
		calls = [
			{"id": call.id, "name": call.function.name, "input": arguments_of(call.function.arguments)}
			for call in message.tool_calls or []
		]
		return Turn(message.content or "", calls, usage=usage_of(response))

	def results(self, messages, rows):
		for row in rows:
			text = f"Error: {row['text']}" if row.get("error") else row["text"]
			messages.append({"role": "tool", "tool_call_id": row["id"], "content": text})


def build(settings, system, tools):
	try:
		target = llm.resolve(settings.get("assistant_model"))
	except llm.ModelError as error:
		raise ProviderError(str(error)) from error
	return Provider(target, system, tools, token_limit(settings.get("assistant_max_tokens")))
