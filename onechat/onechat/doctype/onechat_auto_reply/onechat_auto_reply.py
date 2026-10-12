import re

import frappe
from frappe import _
from frappe.model.document import Document


class OneChatAutoReply(Document):
	# begin: auto-generated types

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		active_when: DF.Literal["Always", "During business hours", "Outside business hours"]
		attach: DF.Attach | None
		cooldown_minutes: DF.Int
		enabled: DF.Check
		keywords: DF.SmallText
		last_replied_at: DF.Datetime | None
		match_type: DF.Literal["Contains", "Exact", "Starts with"]
		message: DF.SmallText
		priority: DF.Int
		reply_count: DF.Int
		rule_name: DF.Data
	# end: auto-generated types

	def validate(self):
		self.rule_name = (self.rule_name or "").strip()
		words = keyword_list(self.keywords)
		if not words:
			frappe.throw(_("Add at least one keyword."))

		self.keywords = "\n".join(words)
		self.message = (self.message or "").strip()
		self.cooldown_minutes = max(self.cooldown_minutes or 0, 0)


def keyword_list(value):
	seen = []
	for word in re.split(r"[,\n]", value or ""):
		word = " ".join(word.split()).lower()
		if word and word not in seen:
			seen.append(word)

	return seen
