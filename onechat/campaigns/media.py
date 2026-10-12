import frappe
from frappe import _
from frappe.query_builder import Order
from frappe.query_builder.functions import Count
from frappe.utils import cint

from onechat.workspace.session import can_use_app

MEDIA_TYPES = ("image", "video", "audio", "document")


@frappe.whitelist()
def library(
	search: str | None = None, media_type: str | None = None, start: int | str = 0, limit: int | str = 40
):
	if not can_use_app():
		frappe.throw(_("You do not have access to OneChat"), frappe.PermissionError)
	from onechat.workspace.session import require_read

	require_read("OneChat Media")

	Media = frappe.qb.DocType("OneChat Media")
	conditions = []

	if media_type in MEDIA_TYPES:
		conditions.append(Media.media_type == media_type)

	text = (search or "").strip()
	if text:
		like = f"%{text}%"
		conditions.append(Media.title.like(like) | Media.tags.like(like) | Media.description.like(like))

	def scoped(query):
		for condition in conditions:
			query = query.where(condition)
		return query

	items = (
		scoped(
			frappe.qb.from_(Media).select(
				Media.name, Media.title, Media.file, Media.media_type, Media.file_size, Media.tags
			)
		)
		.orderby(Media.modified, order=Order.desc)
		.limit(min(max(cint(limit), 1), 100))
		.offset(max(cint(start), 0))
		.run(as_dict=True)
	)
	total = scoped(frappe.qb.from_(Media).select(Count(Media.name))).run()[0][0]

	return {"items": items, "total": total}
