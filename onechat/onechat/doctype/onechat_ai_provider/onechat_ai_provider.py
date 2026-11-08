import frappe
from frappe import _
from frappe.model.document import Document


class OneChatAIProvider(Document):
	def validate(self):
		self.provider_name = (self.provider_name or "").strip()
		self.api_base = (self.api_base or "").strip().rstrip("/") or None
		self.litellm_provider = (self.litellm_provider or "").strip() or ("openai" if self.api_base else None)
		if not self.litellm_provider:
			frappe.throw(_("Set the LiteLLM provider, or an API base for an OpenAI-compatible address."))

	def resolved_key(self):
		return self.get_password("api_key", raise_exception=False) or None
