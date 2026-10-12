import mimetypes

import frappe
from frappe import _
from frappe.model.document import Document

KINDS = ("image", "video", "audio")


class OneChatMedia(Document):
	# begin: auto-generated types

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		description: DF.SmallText | None
		file: DF.Attach
		file_size: DF.Int
		media_type: DF.Literal["image", "video", "audio", "document"]
		tags: DF.SmallText | None
		title: DF.Data
	# end: auto-generated types

	def validate(self):
		if (self.file or "").startswith("/private/"):
			frappe.throw(_("Media files must be public so WhatsApp can fetch them"))

		self.media_type = media_type_of(self.file)
		self.file_size = frappe.db.get_value("File", {"file_url": self.file}, "file_size") or 0
		self.tags = ", ".join(tag.strip() for tag in (self.tags or "").split(",") if tag.strip())


def media_type_of(file_url):
	mime = mimetypes.guess_type((file_url or "").split("?")[0])[0] or ""
	kind = mime.split("/")[0]

	return kind if kind in KINDS else "document"
