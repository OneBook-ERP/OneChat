import frappe
import requests
from frappe.utils import cint

from onechat.assistant.providers import ProviderError, build
from onechat.automation.engine import start_comment_flow
from onechat.inbox.conversations import MESSAGE
from onechat.instagram import comments, graph

ABUSIVE = "Abusive only"
RULES = {
	ABUSIVE: "abusive, hateful, harassing, sexually explicit, threatening, or obvious spam or a scam",
	"Abusive and complaints": (
		"abusive, hateful, harassing, sexually explicit, threatening, obvious spam or a scam, "
		"or an angry complaint or negative review about the business"
	),
}
SYSTEM = (
	"You moderate comments on a business's Instagram posts. "
	"Answer with exactly one word: HIDE if the comment is {rule}; otherwise KEEP. "
	"Questions, praise, neutral remarks and mild criticism are KEEP."
)


def should_hide(text, level):
	provider = build(
		frappe.get_cached_doc(comments.SETTINGS), SYSTEM.format(rule=RULES.get(level, RULES[ABUSIVE])), []
	)
	messages = []
	provider.ask(messages, f"Comment: {text}")
	turn = provider.step(messages)
	return turn.refused or (turn.text or "").strip().upper().startswith("HIDE")


def verdict(doc, config):
	if not cint(config.ig_comment_hide_negative) or not (doc.message or "").strip():
		return False
	try:
		return should_hide(doc.message, config.ig_comment_negative_level)
	except ProviderError:
		frappe.log_error(
			title="Instagram comment: AI check", reference_doctype=MESSAGE, reference_name=doc.name
		)
		return False


def check(doc):
	if cint(doc.comment_hidden):
		return
	if not verdict(doc, comments.settings()):
		start_comment_flow(doc)
		return
	try:
		comments.hide(doc, auto=True)
	except (graph.GraphError, requests.RequestException):
		frappe.log_error(title="Instagram comment: hide", reference_doctype=MESSAGE, reference_name=doc.name)
