import json
import re
import time
import traceback
from collections import deque

import frappe
from frappe import _
from frappe.utils import add_to_date, cint, get_datetime, now_datetime, strip_html

from onechat.automation import safety, steps
from onechat.automation.node_executors import get_node_executor
from onechat.automation.values import as_text, plain, rules_match
from onechat.integrations import links

FLOW = "OneChat Flow"
SESSION = "OneChat Flow Session"
LOG = "Automation Execution Log"
CONTACT = "OneChat Contact"
MESSAGE = "OneChat Message"
TRIGGER_CACHE = "onechat:flow-triggers"
MAX_STEPS = 200
RETRIES = 2
FAILURE_WINDOW = 3600
FAILURE_LIMIT = 5
OPEN = ("Running", "Waiting")
DEFAULT_TIMEOUT_HOURS = 24
DOC_EVENT_TRIGGERS = ("doc_event_trigger", "erpnext_doc_event_trigger")
MESSAGE_TRIGGERS = (
	"message_received",
	"button_clicked",
	"form_submitted",
	"order_placed",
	"chat_link_opened",
	"whatsapp_trigger",
	"whatsapp_incoming_trigger",
	"comment_received",
)
TRIGGERS = (
	*MESSAGE_TRIGGERS,
	*DOC_EVENT_TRIGGERS,
	"scheduled_trigger",
	"manual_trigger",
	"webhook_trigger",
)
SAFE_LEGACY = {
	"set_variable",
	"python_expression",
	"transform_data",
	"filter_array",
	"map_array",
	"merge_objects",
	"loop",
	"switch",
	"switch_case",
	"get_doc",
	"get_document",
	"get_list",
}
SKIP_DOCTYPES = {
	"Error Log",
	LOG,
	"Automation Execution Step",
	SESSION,
	"Activity Log",
	"Version",
	"Comment",
	"Communication",
	"Email Queue",
	FLOW,
	MESSAGE,
	CONTACT,
	"WhatsApp Notification Log",
	"Scheduled Job Log",
	"Route History",
	"Access Log",
}


class FlowError(Exception):
	pass


class Graph:
	def __init__(self, graph_json):
		data = json.loads(graph_json) if isinstance(graph_json, str) else graph_json or {}
		self.nodes = {str(node["id"]): node for node in data.get("nodes") or []}
		self.edges = {}
		for edge in data.get("edges") or []:
			self.edges.setdefault(str(edge["source"]), []).append(edge)

	@staticmethod
	def kind(node):
		data = node.get("data") or {}
		return data.get("nodeType") or node.get("type")

	@staticmethod
	def config(node):
		data = node.get("data") or {}
		return data.get("config") or {}

	def trigger(self):
		for node_id, node in self.nodes.items():
			kind = self.kind(node) or ""
			if kind in TRIGGERS or kind.endswith("_trigger"):
				return node_id
		return None

	def has_output(self, node_id, handle):
		return any((edge.get("sourceHandle") or None) == handle for edge in self.edges.get(node_id, []))

	def following(self, node_id, handle, run):
		targets = []
		for edge in self.edges.get(node_id, []):
			if handle is not None:
				if (edge.get("sourceHandle") or None) != handle:
					continue
			else:
				if edge.get("sourceHandle") == "error":
					continue
				condition = ((edge.get("data") or {}).get("condition") or "").strip()
				if condition and not run.legacy_condition(condition):
					continue
			targets.append(str(edge["target"]))
		return targets


class Run:
	def __init__(self, flow, graph, context, state=None, session=None, simulate=False):
		self.flow = flow
		self.graph = graph
		self.context = context
		self.state = state or {"retries": {}}
		self.session = session
		self.simulate = simulate
		self.outbox = []
		self.steps = []
		self.waiting = None
		self.ended = False
		self.stop_reason = None
		self.path = []

	@property
	def contact(self):
		return (self.context.get("contact") or {}).get("name")

	@property
	def phone(self):
		contact = self.context.get("contact") or {}
		return (
			contact.get("mobile_no")
			or contact.get("instagram_id")
			or (self.session.phone if self.session else None)
		)

	def effect(self, description):
		if self.simulate:
			self.note(description)
			return False
		return True

	def note(self, text):
		self.outbox.append({"from": "system", "text": text})

	def send(self, options=None, kind=None, **values):
		if self.simulate:
			bubble = {
				"from": "bot",
				"text": values.get("message") or "",
				"type": values.get("content_type") or "text",
			}
			if options:
				bubble.update({"options": options, "kind": kind})
			if values.get("attach"):
				bubble["attach"] = values["attach"]
			if values.get("template"):
				bubble.update(
					{
						"type": "template",
						"text": _("Template: {0}").format(values["template"]),
					}
				)
			if values.get("flow"):
				bubble.update({"type": "form", "form": values["flow"]})
			self.outbox.append(bubble)
			return None

		if not self.phone:
			raise FlowError(
				_(
					"There is no one to send to. Start the flow from a customer message or set the phone field on the trigger."
				)
			)

		references = {"reference_doctype": CONTACT, "reference_name": self.contact} if self.contact else {}
		return self.send_to(self.phone, **references, **values)

	def send_to(self, phone, **values):
		account = self.session.whatsapp_account if self.session else None
		comment = self.context.get("comment")
		if comment and not comment.get("replied"):
			values["reply_to_comment"] = comment["id"]
			comment["replied"] = True
		doc = frappe.get_doc(
			{
				"doctype": MESSAGE,
				"type": "Outgoing",
				"message_type": values.pop("message_type", "Manual"),
				"source": "Bot",
				"to": phone,
				"whatsapp_account": account,
				**values,
			}
		)
		doc.flags.onechat_flow = True
		doc.insert(ignore_permissions=True)
		return doc.name

	def legacy_condition(self, condition):
		from onechat.automation.flow_runner import evaluate

		return evaluate(condition, self.context)

	def execute(self, start):
		queue = deque(start)
		count = 0
		while queue and not self.ended:
			count += 1
			if count > MAX_STEPS:
				raise FlowError(
					_(
						"The flow stopped after {0} steps. Check for a loop without a question or wait in it."
					).format(MAX_STEPS)
				)

			node_id = queue.popleft()
			node = self.graph.nodes.get(node_id)
			if not node:
				continue

			result = self.step(node_id, node)
			if result.end:
				self.ended = True
				break
			if result.wait:
				self.pause(node_id, result)
				continue

			queue.extendleft(reversed(self.graph.following(node_id, result.handle, self)))

	def pause(self, node_id, result):
		if self.waiting and self.waiting["node"] != node_id:
			self.log(
				node_id,
				Graph.kind(self.graph.nodes[node_id]),
				"Skipped",
				output={"reason": "Another step is already waiting"},
			)
			return

		hours = cint(getattr(self.flow, "reply_timeout_hours", 0)) or DEFAULT_TIMEOUT_HOURS
		minutes = result.minutes if result.minutes else (None if result.wait == "Timer" else hours * 60)
		self.waiting = {
			"node": node_id,
			"kind": result.wait,
			"resume_at": (add_to_date(now_datetime(), minutes=minutes) if minutes else None),
		}

	def step(self, node_id, node):
		kind = Graph.kind(node)
		config = Graph.config(node)
		self.path.append(node_id)
		attempt = 0
		while True:
			try:
				handler = steps.STEPS.get(kind)
				if handler:
					result = handler(self, node_id, config)
				else:
					result = self.legacy(kind, node)
				self.log(node_id, kind, "Success", output=result.output)
				return result
			except Exception as error:
				if attempt < RETRIES and not self.simulate and safety.transient(error):
					attempt += 1
					time.sleep(attempt)
					continue
				return self.fail(node_id, node, kind, config, error)

	def fail(self, node_id, node, kind, config, error):
		message, hint = safety.friendly(error, config.get("doctype"))
		text = f"{message}\n{hint}" if hint else message
		self.log(node_id, kind, "Failed", error=text)
		if self.graph.has_output(node_id, "error"):
			self.context["error"] = {
				"step": (node.get("data") or {}).get("label") or kind,
				"message": message,
				"hint": hint,
			}
			return steps.Result(handle="error", output={"handled": message})
		raise FlowError(text) from error

	def legacy(self, kind, node):
		executor = get_node_executor(kind)
		if not executor:
			return steps.Result(output={"skipped": _("This step type is not supported")})
		if self.simulate and kind not in SAFE_LEGACY:
			self.note(_("Skipped in test chat: {0}").format(kind.replace("_", " ")))
			return steps.Result()

		self.context = executor(node, self.context) or self.context
		return steps.Result(output=self.context.get("last_output"))

	def resume(self, node_id, event):
		node = self.graph.nodes.get(node_id)
		if not node:
			return

		kind = Graph.kind(node)
		handler = steps.RESUME.get(kind)
		self.path.append(node_id)
		if not handler:
			self.execute(self.graph.following(node_id, None, self))
			return

		try:
			result = handler(self, node_id, Graph.config(node), event)
			self.log(
				node_id,
				kind,
				"Success",
				output=result.output or {"resumed": event["kind"]},
			)
		except Exception as error:
			result = self.fail(node_id, node, kind, Graph.config(node), error)

		if result.end:
			self.ended = True
		elif result.wait:
			self.pause(node_id, result)
		else:
			self.execute(self.graph.following(node_id, result.handle, self))

	def log(self, node_id, kind, status, output=None, error=None):
		self.steps.append(
			{
				"node_id": node_id,
				"node_type": kind,
				"status": status,
				"output": (json.dumps(plain(output), default=str)[:5000] if output else None),
				"error": error,
				"timestamp": now_datetime(),
			}
		)


def clear_trigger_cache(doc=None, method=None):
	frappe.cache().delete_value(TRIGGER_CACHE)


def trigger_index():
	cached = frappe.cache().get_value(TRIGGER_CACHE)
	if cached is not None:
		return cached

	rows = []
	for flow in frappe.get_all(FLOW, filters={"is_active": 1}, fields=["name", "graph_json"]):
		try:
			graph = Graph(flow.graph_json or "{}")
		except (ValueError, KeyError, TypeError):
			continue
		node_id = graph.trigger()
		if node_id:
			node = graph.nodes[node_id]
			rows.append(
				{
					"flow": flow.name,
					"kind": Graph.kind(node),
					"config": Graph.config(node),
				}
			)

	frappe.cache().set_value(TRIGGER_CACHE, rows, expires_in_sec=6 * 3600)
	return rows


def display_name(row):
	name = (row.contact_name or "").strip()
	digits = "".join(ch for ch in name if ch.isdigit())
	if not name or (
		digits and len(digits) >= 7 and len(digits) >= len(name.replace(" ", "").replace("+", "")) - 1
	):
		return _("there")
	return name


def contact_context(name):
	row = frappe.db.get_value(
		CONTACT,
		name,
		[
			"name",
			"contact_name",
			"mobile_no",
			"email",
			"assigned_to",
			"conversation_status",
			"reference_doctype",
			"reference_docname",
			"opted_out",
			"channel",
			"instagram_id",
		],
		as_dict=True,
	)
	if not row:
		return {}

	labels = frappe.get_all(
		"OneChat Contact Label",
		filters={"parenttype": CONTACT, "parentfield": "labels", "parent": name},
		pluck="label",
	)
	contact = plain(dict(row))
	contact["first_name"] = (row.contact_name or "").split(" ")[0]
	contact["display_name"] = display_name(row)
	contact["labels"] = labels
	contact["links"] = {
		row.integration: {"doctype": row.doctype, "name": row.name} for row in links.of(name) if row.main
	}
	return contact


def message_context(doc):
	extra = frappe.parse_json(doc.get("buttons")) if doc.get("buttons") else {}
	form = frappe.parse_json(doc.get("flow_response")) if doc.get("flow_response") else None
	return {
		"id": doc.name,
		"type": doc.content_type,
		"text": strip_html(doc.message or "").strip(),
		"reply_id": (extra or {}).get("reply_id") if isinstance(extra, dict) else None,
		"form": form if isinstance(form, dict) else None,
		"form_name": doc.get("flow"),
		"attach": doc.get("attach"),
	}


def load_flow(name):
	return frappe.get_doc(FLOW, name)


def new_log(flow, session, context):
	return frappe.get_doc(
		{
			"doctype": LOG,
			"flow": flow.name,
			"run_id": session.name[:10],
			"contact": session.contact,
			"status": "Running",
			"start_time": now_datetime(),
			"trigger_data": json.dumps(plain(context), indent=1, default=str)[:20000],
		}
	).insert(ignore_permissions=True)


def stop_open_sessions(contact, reason, exclude=None):
	if not contact:
		return
	for name in frappe.get_all(SESSION, filters={"contact": contact, "status": ["in", OPEN]}, pluck="name"):
		if name != exclude:
			end_session(frappe.get_doc(SESSION, name), "Stopped", reason)


def end_session(session, status, reason=None):
	session.status = status
	session.stop_reason = reason
	session.resume_at = None
	session.waiting_for = None
	session.save(ignore_permissions=True)
	if session.execution_log and status != "Completed":
		frappe.db.set_value(
			LOG,
			session.execution_log,
			{"status": "Cancelled", "end_time": now_datetime()},
			update_modified=False,
		)
	sync_contact(session)


def sync_contact(session):
	if not session.contact:
		return

	current = frappe.db.get_value(CONTACT, session.contact, "bot_session")
	if session.status in OPEN:
		values = {"bot_flow": session.flow, "bot_session": session.name}
		from onechat.inbox import history

		history.bot_started(session.contact, session.flow)
	elif current == session.name:
		values = {"bot_flow": None, "bot_session": None}
	else:
		return

	frappe.db.set_value(CONTACT, session.contact, values, update_modified=False)
	from onechat.inbox.conversations import publish

	publish(session.contact)


def start(flow_name, context, contact=None, phone=None, account=None):
	flow = load_flow(flow_name)
	graph = Graph(flow.graph_json or "{}")
	trigger = graph.trigger()
	if not trigger:
		raise FlowError(_("Flow {0} has no trigger.").format(flow_name))

	if contact:
		context["contact"] = contact_context(contact)
		stop_open_sessions(contact, _("Another flow started"))

	session = frappe.get_doc(
		{
			"doctype": SESSION,
			"flow": flow.name,
			"contact": contact,
			"phone": phone
			or (context.get("contact") or {}).get("mobile_no")
			or (context.get("contact") or {}).get("instagram_id"),
			"whatsapp_account": account,
			"status": "Running",
		}
	).insert(ignore_permissions=True)
	log = new_log(flow, session, context)
	session.execution_log = log.name

	context.setdefault("answers", {})
	context.setdefault("vars", {})
	run = Run(flow, graph, context, session=session)
	error = None
	try:
		run.execute([trigger])
	except Exception as exc:
		error = exc
	finish(run, session, log, error)
	frappe.db.set_value(FLOW, flow.name, "run_count", cint(flow.run_count) + 1, update_modified=False)
	return session


def resume(session, event):
	flow = load_flow(session.flow)
	graph = Graph(flow.graph_json or "{}")
	if session.current_node and session.current_node not in graph.nodes:
		end_session(
			session,
			"Stopped",
			_("The step this chat was waiting on was removed from the flow"),
		)
		return session
	saved = json.loads(session.context_json or "{}")
	context = saved.get("context") or {}
	if session.contact:
		context["contact"] = contact_context(session.contact)
	if event.get("message"):
		context["message"] = event["message"]

	run = Run(flow, graph, context, state=saved.get("state"), session=session)
	log = (
		frappe.get_doc(LOG, session.execution_log)
		if session.execution_log and frappe.db.exists(LOG, session.execution_log)
		else new_log(flow, session, context)
	)
	session.execution_log = log.name
	session.status = "Running"
	error = None
	try:
		run.resume(session.current_node, event)
	except Exception as exc:
		error = exc
	finish(run, session, log, error)
	return session


def finish(run, session, log, error=None):
	for row in run.steps:
		log.append("execution_steps", row)

	if error:
		message = str(error)
		if not isinstance(error, FlowError):
			message = f"{error}\n\n{traceback.format_exc()}"
		session.update(
			{
				"status": "Failed",
				"stop_reason": message[:140],
				"resume_at": None,
				"waiting_for": None,
			}
		)
		log.update(
			{
				"status": "Failed",
				"error_message": message,
				"end_time": now_datetime(),
				"error_node_id": run.path[-1] if run.path else None,
			}
		)
		fallback(run, session, str(error))
		track_failure(run.flow, str(error))
	elif run.waiting and not run.ended:
		session.update(
			{
				"status": "Waiting",
				"current_node": run.waiting["node"],
				"waiting_for": run.waiting["kind"],
				"resume_at": run.waiting["resume_at"],
			}
		)
		log.status = "Waiting"
	else:
		session.update(
			{
				"status": "Completed",
				"resume_at": None,
				"waiting_for": None,
				"stop_reason": run.stop_reason,
			}
		)
		log.update({"status": "Success", "end_time": now_datetime()})

	session.context_json = json.dumps({"context": plain(run.context), "state": run.state}, default=str)
	log.context_json = json.dumps(plain(run.context), indent=1, default=str)[:50000]
	log.save(ignore_permissions=True)
	session.save(ignore_permissions=True)
	sync_contact(session)


def fallback(run, session, message):
	flow = run.flow
	if not session.contact:
		return
	text = (flow.get("error_message") or "").strip()
	try:
		if cint(flow.get("error_handover")):
			config = {
				"text": text,
				"note": _("The flow {0} stopped: {1}").format(flow.name, message[:300]),
			}
			if not frappe.db.get_value(CONTACT, session.contact, "assigned_to"):
				config.update(
					{"mode": "team", "team": flow.error_team}
					if flow.get("error_team")
					else {"mode": "round_robin"}
				)
			steps.handover(run, None, config)
		elif text:
			run.send(content_type="text", message=text)
	except Exception:
		frappe.log_error(title=f"OneChat flow fallback: {flow.name}")


def track_failure(flow, message):
	key = f"onechat:flow-failures:{flow.name}"
	now = time.time()
	stamps = [stamp for stamp in frappe.cache().get_value(key) or [] if now - stamp < FAILURE_WINDOW] + [now]
	frappe.cache().set_value(key, stamps, expires_in_sec=FAILURE_WINDOW)
	if len(stamps) < FAILURE_LIMIT:
		return
	alerted = f"onechat:flow-alerted:{flow.name}"
	if frappe.cache().get_value(alerted):
		return
	frappe.cache().set_value(alerted, 1, expires_in_sec=FAILURE_WINDOW)

	paused = False
	if cint(flow.get("error_pause")) and cint(flow.get("is_active")):
		frappe.db.set_value(FLOW, flow.name, "is_active", 0)
		clear_trigger_cache()
		paused = True
	if not (cint(flow.get("error_notify")) or paused):
		return

	from onechat.insights.costs import admins

	subject = (
		_("{0} was paused after failing {1} times in an hour: {2}")
		if paused
		else _("{0} failed {1} times in the last hour: {2}")
	).format(flow.name, len(stamps), message.splitlines()[0][:160] if message else "")
	for user in admins():
		frappe.get_doc(
			{
				"doctype": "Notification Log",
				"subject": subject,
				"for_user": user,
				"type": "Alert",
				"document_type": FLOW,
				"document_name": flow.name,
			}
		).insert(ignore_permissions=True)


def waiting_session(contact):
	names = frappe.get_all(
		SESSION,
		filters={
			"contact": contact,
			"status": "Waiting",
			"waiting_for": ["in", ["Reply", "Form"]],
		},
		pluck="name",
		order_by="modified desc",
		limit_page_length=1,
	)
	return frappe.get_doc(SESSION, names[0], for_update=True) if names else None


def normalized(text):
	return " ".join(strip_html(as_text(text)).split()).lower()


def first_message(doc, contact):
	return not frappe.db.exists(
		MESSAGE,
		{"whatsapp_contact": contact, "type": "Incoming", "name": ["!=", doc.name]},
	)


def replied_template(doc):
	if not doc.get("reply_to_message_id"):
		return None
	return frappe.db.get_value(MESSAGE, {"message_id": doc.reply_to_message_id}, "template")


def keyword_hit(config, text):
	from onechat.inbox.auto_reply import matches

	mode = {"exact": "Exact", "starts_with": "Starts with"}.get(config.get("keyword_match"), "Contains")
	words = [word.get("value") if isinstance(word, dict) else word for word in config.get("keywords") or []]
	keywords = [normalized(word) for word in words if normalized(word)]
	return any(matches(text, word, mode) for word in keywords)


SHORTCODE = re.compile(r"instagram\.com/(?:[^/?#]+/)?(?:p|reels?|tv)/([^/?#]+)", re.I)


def shortcode(link):
	match = SHORTCODE.search(link or "")
	return match.group(1) if match else None


def post_matches(config, doc):
	rows = [row if isinstance(row, dict) else {"value": row} for row in config.get("posts") or []]
	rows = [row for row in rows if str(row.get("value") or row.get("id") or "").strip()]
	if not rows:
		return True
	media_id = doc.get("media_id")
	link = (doc.get("link_url") or "").split("?")[0].rstrip("/")
	code = shortcode(link)
	for row in rows:
		value = str(row.get("value") or "").strip()
		if media_id and media_id in (str(row.get("id") or ""), value):
			return True
		if link and value.split("?")[0].rstrip("/") == link:
			return True
		if code and shortcode(value) == code:
			return True
	return False


def replied_before(doc, contact):
	from onechat.instagram.comments import replied_before as replied

	return replied(doc, contact)


def comment_score(config, doc, text, contact):
	if doc.get("comment_hidden") or not post_matches(config, doc):
		return 0
	if (config.get("match") or "keywords") == "keywords" and not (text and keyword_hit(config, text)):
		return 0
	if cint(config.get("once_per_person", 1)) and replied_before(doc, contact):
		return 0
	return 55


def trigger_score(row, doc, message, contact):
	kind, config = row["kind"], row["config"]
	text = normalized(message["text"])

	if (doc.content_type == "comment") != (kind == "comment_received"):
		return 0
	if kind == "comment_received":
		return comment_score(config, doc, text, contact)

	if kind == "form_submitted":
		return (
			60
			if doc.content_type == "flow" and (not config.get("form") or doc.get("flow") == config["form"])
			else 0
		)
	if kind == "button_clicked":
		if doc.content_type != "button":
			return 0
		if config.get("button") and text != normalized(config["button"]):
			return 0
		if config.get("template") and replied_template(doc) != config["template"]:
			return 0
		return 50
	if kind == "order_placed":
		return 45 if doc.content_type == "order" else 0
	if kind == "chat_link_opened":
		from onechat.campaigns.chat_links import REF

		found = REF.search(doc.message or "") if doc.content_type == "text" else None
		if not found or not config.get("link"):
			return 0
		code = frappe.db.get_value("OneChat Chat Link", config["link"], "ref_code")
		return 40 if code and code.upper() == found.group(1).upper() else 0
	if kind == "message_received":
		if doc.content_type in ("reaction", "flow", "order"):
			return 0
		mode = config.get("match") or "any"
		if mode == "keywords":
			return 30 if text and keyword_hit(config, text) else 0
		if mode == "first":
			return 20 if first_message(doc, contact) else 0
		return 10
	if kind in ("whatsapp_trigger", "whatsapp_incoming_trigger"):
		if config.get("keyword") and normalized(config["keyword"]) not in text:
			return 0
		if config.get("button") and text != normalized(config["button"]):
			return 0
		if config.get("template_name") and replied_template(doc) != config["template_name"]:
			return 0
		return 30 if any(config.get(key) for key in ("keyword", "button", "template_name")) else 0
	return 0


def agent_talking(contact):
	from onechat.inbox.history import current

	name = current(contact)
	return bool(name and cint(frappe.db.get_value("OneChat Conversation", name, "agent_replies")))


def channel_fits(config, channel):
	return (config.get("channel") or "WhatsApp") in ("Any", channel)


def matching_flow(doc, message, contact):
	best = None
	busy = None
	channel = doc.get("channel") or "WhatsApp"
	for row in trigger_index():
		if row["kind"] not in MESSAGE_TRIGGERS:
			continue
		if row["kind"] != "comment_received" and not channel_fits(row["config"], channel):
			continue
		if row["kind"] == "message_received":
			if busy is None:
				busy = agent_talking(contact)
			if busy:
				continue
		score = trigger_score(row, doc, message, contact)
		if score and (not best or score > best[0]):
			best = (score, row["flow"])
	return best[1] if best else None


def on_message(doc, method=None):
	if (
		doc.type != "Incoming"
		or doc.content_type == "reaction"
		or doc.flags.get("onechat_consent_keyword")
		or doc.flags.get("onechat_survey")
	):
		return

	contact = doc.get("whatsapp_contact")
	if not contact:
		return

	if doc.content_type == "comment":
		if not doc.flags.get("onechat_skip_flow"):
			doc.flags.onechat_flow_handled = start_comment_flow(doc)
		return

	frappe.db.savepoint("onechat_flow")
	try:
		message = message_context(doc)
		if doc.content_type == "order" and start_order_flow(doc, message, contact):
			return

		session = waiting_session(contact)
		if session:
			doc.flags.onechat_flow_handled = True
			resume(session, {"kind": "reply", "message": message})
			return

		flow = matching_flow(doc, message, contact)
		if flow:
			doc.flags.onechat_flow_handled = True
			start(
				flow,
				{"trigger": "message", "message": message},
				contact=contact,
				account=doc.get("whatsapp_account"),
			)
	except Exception:
		frappe.db.rollback(save_point="onechat_flow")
		frappe.log_error(title="OneChat flow", reference_doctype=MESSAGE, reference_name=doc.name)


def start_order_flow(doc, message, contact):
	channel = doc.get("channel") or "WhatsApp"
	flow = next(
		(
			row["flow"]
			for row in trigger_index()
			if row["kind"] == "order_placed" and channel_fits(row["config"], channel)
		),
		None,
	)
	if not flow:
		return False

	from onechat.integrations.erpnext_commerce import order_details

	order = {**order_details(frappe.parse_json(doc.get("products") or "{}")), "message": doc.name}
	start(
		flow,
		{"trigger": "message", "message": message, "order": order},
		contact=contact,
		account=doc.get("whatsapp_account"),
	)
	doc.flags.onechat_flow_handled = doc.flags.onechat_order_flow = True
	return True


def start_comment_flow(doc):
	contact = doc.get("whatsapp_contact")
	if not contact or cint(doc.get("comment_hidden")):
		return False
	try:
		message = message_context(doc)
		flow = matching_flow(doc, message, contact)
	except Exception:
		frappe.log_error(
			title="OneChat comment flow",
			reference_doctype=MESSAGE,
			reference_name=doc.name,
		)
		return False
	if not flow:
		return False
	from onechat.instagram.comments import show_in_inbox

	show_in_inbox(doc)
	comment_actions(flow, doc)
	context = {
		"trigger": "message",
		"message": message,
		"comment": {
			"id": doc.message_id,
			"media_id": doc.get("media_id"),
			"link": doc.get("link_url"),
		},
	}
	frappe.db.savepoint("onechat_comment_flow")
	try:
		start(flow, context, contact=contact, account=doc.get("whatsapp_account"))
	except Exception:
		frappe.db.rollback(save_point="onechat_comment_flow")
		frappe.log_error(
			title="OneChat comment flow",
			reference_doctype=MESSAGE,
			reference_name=doc.name,
		)
	return True


def on_doc_event(doc, method=None):
	if frappe.flags.in_migrate or frappe.flags.in_install or frappe.flags.in_patch or frappe.flags.in_import:
		return
	if doc.doctype in SKIP_DOCTYPES or (doc.meta and doc.meta.istable):
		return

	if doc_event_rows(doc.doctype, method):
		doc_event(doc.doctype, doc.name, method, plain(doc.as_dict()))


def doc_event_rows(doctype, method):
	return [
		row
		for row in trigger_index()
		if row["kind"] in DOC_EVENT_TRIGGERS
		and row["config"].get("doctype") == doctype
		and row["config"].get("event") == method
	]


def doc_event(doctype, name, method, data):
	rows = doc_event_rows(doctype, method)
	if not rows:
		return

	context = {
		"trigger": "doc_event",
		"doc": data,
		"erp": {"doctype": doctype, "name": name, "doc": data},
		"doctype": doctype,
		"docname": name,
	}
	for row in rows:
		if not rules_match(row["config"], context, steps.EXTRA_RULES):
			continue
		frappe.enqueue(
			"onechat.automation.engine.run_doc_event",
			queue="short",
			flow=row["flow"],
			context=context,
			phone_field=row["config"].get("phone_field"),
			enqueue_after_commit=True,
		)


def contact_for_phone(phone, name=None):
	from onechat.inbox.conversations import digits, find_contact

	if not digits(phone):
		return None
	existing = find_contact(phone)
	if existing:
		return existing

	return (
		frappe.get_doc({"doctype": CONTACT, "contact_name": name or phone, "mobile_no": phone})
		.insert(ignore_permissions=True)
		.name
	)


def run_doc_event(flow, context, phone_field=None):
	doc = context.get("doc") or {}
	phone = doc.get(phone_field) if phone_field else None
	contact = None
	if phone:
		name = (
			doc.get("customer_name") or doc.get("contact_display") or doc.get("lead_name") or doc.get("title")
		)
		contact = contact_for_phone(phone, name)

	try:
		start(flow, context, contact=contact, phone=phone)
	except Exception:
		frappe.log_error(title=f"OneChat flow {flow}")


def start_manual(flow, contact):
	return start(flow, {"trigger": "manual"}, contact=contact)


def stop_contact(contact, reason):
	stop_open_sessions(contact, reason)


def stop_for_agent(contact):
	session = frappe.db.get_value(CONTACT, contact, "bot_session")
	if not session or frappe.db.get_value(SESSION, session, "status") not in OPEN:
		return
	flow = frappe.db.get_value(SESSION, session, "flow")
	if cint(frappe.db.get_value(FLOW, flow, "stop_on_agent_reply") if flow else 1):
		end_session(frappe.get_doc(SESSION, session), "Stopped", _("An agent replied"))


def cron_of(config):
	if config.get("frequency") == "cron":
		return (config.get("schedule") or "").strip() or None

	hour, minute = 9, 0
	if config.get("time"):
		parts = str(config["time"]).split(":")
		hour, minute = cint(parts[0]), cint(parts[1]) if len(parts) > 1 else 0

	frequency = config.get("frequency") or ("cron" if config.get("schedule") else "daily")
	if frequency == "cron":
		return (config.get("schedule") or "").strip() or None
	if frequency == "hourly":
		return f"{minute} * * * *"
	if frequency == "weekly":
		return f"{minute} {hour} * * {cint(config.get('weekday'))}"
	if frequency == "monthly":
		return f"{minute} {hour} {max(min(cint(config.get('day')) or 1, 28), 1)} * *"
	return f"{minute} {hour} * * *"


def run_schedules():
	from croniter import croniter

	now = now_datetime()
	for row in trigger_index():
		if row["kind"] != "scheduled_trigger":
			continue
		expression = cron_of(row["config"])
		if not expression or not croniter.is_valid(expression):
			continue

		last = frappe.db.get_value(FLOW, row["flow"], "last_scheduled_run")
		if not last:
			frappe.db.set_value(FLOW, row["flow"], "last_scheduled_run", now, update_modified=False)
			continue
		if croniter(expression, get_datetime(last)).get_next(type(now)) > now:
			continue

		frappe.db.set_value(FLOW, row["flow"], "last_scheduled_run", now, update_modified=False)
		frappe.db.commit()  # nosemgrep: frappe-manual-commit - update schedule timestamp before execution
		try:
			start(row["flow"], {"trigger": "schedule", "scheduled_at": str(now)})
			frappe.db.commit()  # nosemgrep: frappe-manual-commit - commit scheduled flow execution state
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title=f"OneChat scheduled flow {row['flow']}")


def resume_due(limit=100):
	due = frappe.get_all(
		SESSION,
		filters={"status": "Waiting", "resume_at": ["<=", now_datetime()]},
		pluck="name",
		order_by="resume_at asc",
		limit_page_length=limit,
	)
	for name in due:
		try:
			session = frappe.get_doc(SESSION, name, for_update=True)
			if (
				session.status != "Waiting"
				or not session.resume_at
				or get_datetime(session.resume_at) > now_datetime()
			):
				continue
			resume(
				session,
				{"kind": "timer" if session.waiting_for == "Timer" else "timeout"},
			)
			frappe.db.commit()  # nosemgrep: frappe-manual-commit - commit resumed flow session state per loop
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title=f"OneChat flow session {name}")


def tick():
	resume_due()
	run_schedules()


def sample_order():
	items = [
		{"item_code": "SAMPLE-1", "item_name": _("Sample item"), "qty": 2, "rate": 250, "amount": 500},
		{"item_code": "SAMPLE-2", "item_name": _("Another item"), "qty": 1, "rate": 400, "amount": 400},
	]
	for row in items:
		row["known"] = True
	return {
		"items": items,
		"summary": "\n".join(f"{row['qty']} × {row['item_name']} · {row['rate']}" for row in items),
		"count": 2,
		"quantity": 3,
		"total": 900,
		"currency": None,
		"note": _("Please deliver in the evening"),
		"unknown": [],
		"message": None,
	}


def simulate(graph_json, state=None, reply=None):
	graph = Graph(graph_json)
	flow = frappe._dict(name="test", reply_timeout_hours=DEFAULT_TIMEOUT_HOURS)
	state = state or {}
	context = state.get("context") or {
		"trigger": "test",
		"contact": {
			"name": None,
			"contact_name": _("Test customer"),
			"display_name": _("Test customer"),
			"first_name": _("Test"),
			"mobile_no": "910000000000",
			"email": "customer@example.com",
			"labels": [],
		},
		"answers": {},
		"vars": {},
	}
	trigger = graph.trigger()
	if not state and trigger and Graph.kind(graph.nodes[trigger]) == "order_placed":
		context["order"] = sample_order()
	run = Run(flow, graph, context, state=state.get("state"), simulate=True)

	try:
		if reply is None:
			trigger = graph.trigger()
			if not trigger:
				raise FlowError(_("Add a trigger first."))
			run.execute([trigger])
		else:
			message = {
				"type": reply.get("type") or "text",
				"text": reply.get("text") or "",
				"reply_id": reply.get("reply_id"),
				"form": reply.get("form"),
			}
			context["message"] = message
			waiting = state.get("waiting") or {}
			if not waiting.get("node"):
				raise FlowError(_("The flow is not waiting for a reply."))
			event = {"kind": reply.get("event") or "reply", "message": message}
			run.resume(waiting["node"], event)
	except Exception as error:
		run.outbox.append({"from": "error", "text": str(error)})
		return {"messages": run.outbox, "path": run.path, "done": True, "state": None}

	done = run.ended or not run.waiting
	return {
		"messages": run.outbox,
		"path": run.path,
		"done": done,
		"waiting": (None if done else {"node": run.waiting["node"], "kind": run.waiting["kind"]}),
		"state": (
			None
			if done
			else {
				"context": plain(run.context),
				"state": run.state,
				"waiting": {"node": run.waiting["node"], "kind": run.waiting["kind"]},
			}
		),
	}


def comment_actions(flow, doc):
	from onechat.instagram.comments import run_flow_actions

	row = next((row for row in trigger_index() if row["flow"] == flow), None)
	run_flow_actions(row["config"] if row else {}, doc)
