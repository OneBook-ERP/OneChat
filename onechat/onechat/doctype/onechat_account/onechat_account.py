import frappe
from frappe.model.document import Document


class OneChatAccount(Document):
	def validate(self):
		if self.channel == "Instagram":
			self.is_default_incoming = 0
			self.is_default_outgoing = 0

	def on_update(self):
		self.there_must_be_only_one_default()

	def there_must_be_only_one_default(self):
		for field in ("is_default_incoming", "is_default_outgoing"):
			if not self.get(field):
				continue

			for whatsapp_account in frappe.get_all("OneChat Account", filters={field: 1}):
				if whatsapp_account.name == self.name:
					continue

				whatsapp_account = frappe.get_doc("OneChat Account", whatsapp_account.name)
				whatsapp_account.set(field, 0)
				whatsapp_account.save()
