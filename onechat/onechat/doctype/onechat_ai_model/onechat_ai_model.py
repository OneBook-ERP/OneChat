from frappe.model.document import Document


class OneChatAIModel(Document):
	def autoname(self):
		self.name = full_name(self.provider, self.model_id)

	def validate(self):
		self.model_id = (self.model_id or "").strip()
		self.label = (self.label or "").strip() or self.model_id


def full_name(provider, model_id):
	return f"{provider}: {model_id.strip()}"
