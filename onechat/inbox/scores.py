import frappe
from frappe import _
from frappe.query_builder.functions import Count, Lower, Max
from frappe.utils import (
    add_days,
    cint,
    date_diff,
    flt,
    get_datetime,
    getdate,
    now_datetime,
    nowdate,
    time_diff_in_seconds,
)

from onechat import integrations
from onechat.inbox.conversations import CONTACT, MESSAGE, guard
from onechat.inbox.visibility import check as check_visible
from onechat.integrations import links
from onechat.workspace.session import require_admin

CONVERSATION = "OneChat Conversation"
WINDOW = 90
BATCH = 500
TOP_VALUE = "onechat:scores:top_value"
PURCHASE_FIELDS = (
    "lifetime_value",
    "order_count",
    "outstanding_amount",
    "first_purchase_on",
    "last_purchase_on",
    "favourite_category",
)
GROUPS = {
    "Champion": {
        "theme": "green",
        "hint": "Buys often, bought recently and spends the most",
    },
    "Loyal": {
        "theme": "green",
        "hint": "Buys regularly and bought in the last 3 months",
    },
    "New customer": {"theme": "blue", "hint": "First purchase in the last 45 days"},
    "Promising": {"theme": "blue", "hint": "Bought recently but only once or twice"},
    "Needs attention": {
        "theme": "amber",
        "hint": "Last purchase was 3 to 6 months ago",
    },
    "At risk": {
        "theme": "red",
        "hint": "Used to buy regularly, nothing in over 6 months",
    },
    "Lost": {"theme": "gray", "hint": "No purchase in over a year"},
    "Prospect": {"theme": "gray", "hint": "Has not bought anything yet"},
}


def value_group(stats, top, today):
    orders = cint(stats.get("order_count"))
    if not orders or not stats.get("last_purchase_on"):
        return "Prospect"
    idle = date_diff(today, stats["last_purchase_on"])
    age = date_diff(today, stats.get("first_purchase_on") or stats["last_purchase_on"])
    if idle > 365:
        return "Lost"
    if idle > 180:
        return "At risk" if orders >= 2 else "Lost"
    if idle > 90:
        return "Needs attention"
    if age <= 45 and orders <= 2:
        return "New customer"
    if idle <= 45 and (
        orders >= 5 or (top and flt(stats.get("lifetime_value")) >= top)
    ):
        return "Champion"
    if orders >= 3:
        return "Loyal"
    return "Promising"


def recency_points(last_reply, now):
    if not last_reply:
        return 0
    days = time_diff_in_seconds(now, last_reply) / 86400
    for limit, points in ((7, 40), (30, 30), (90, 15), (180, 5)):
        if days <= limit:
            return points
    return 0


def engagement(activity, now):
    points = recency_points(activity.get("last_reply_at"), now)
    points += min(25, cint(activity.get("replies")) * 2.5)
    points += min(15, cint(activity.get("conversations")) * 5)
    sent = cint(activity.get("sent"))
    points += 20 * cint(activity.get("read")) / sent if sent else 0
    return max(0, min(100, round(points)))


def activity(names):
    since = add_days(now_datetime(), -WINDOW)
    out = {name: {} for name in names}
    message = frappe.qb.DocType(MESSAGE)
    incoming = (message.type == "Incoming") & message.whatsapp_contact.isin(names)
    for contact, last in (
        frappe.qb.from_(message)
        .select(message.whatsapp_contact, Max(message.creation))
        .where(incoming)
        .groupby(message.whatsapp_contact)
        .run()
    ):
        out[contact]["last_reply_at"] = last
    for contact, count in (
        frappe.qb.from_(message)
        .select(message.whatsapp_contact, Count("*"))
        .where(incoming & (message.creation >= since))
        .groupby(message.whatsapp_contact)
        .run()
    ):
        out[contact]["replies"] = count
    for contact, status, count in (
        frappe.qb.from_(message)
        .select(message.whatsapp_contact, Lower(message.status), Count("*"))
        .where(
            (message.type == "Outgoing")
            & (message.creation >= since)
            & message.whatsapp_contact.isin(names)
        )
        .groupby(message.whatsapp_contact, Lower(message.status))
        .run()
    ):
        if status == "failed":
            continue
        out[contact]["sent"] = cint(out[contact].get("sent")) + count
        if status == "read":
            out[contact]["read"] = count
    conversation = frappe.qb.DocType(CONVERSATION)
    for contact, count in (
        frappe.qb.from_(conversation)
        .select(conversation.contact, Count("*"))
        .where((conversation.opened_at >= since) & conversation.contact.isin(names))
        .groupby(conversation.contact)
        .run()
    ):
        out[contact]["conversations"] = count
    return out


def purchases(contacts):
    out = {}
    by_doctype = {}
    measured = integrations.metric_doctypes()
    records = links.pairs(contacts)
    for row in contacts:
        record = next(
            (
                (doctype, name)
                for doctype, name in records.get(row.name, [])
                if doctype in measured
            ),
            None,
        )
        if record:
            by_doctype.setdefault(record[0], []).append((row.name, record[1]))
    for doctype, rows in by_doctype.items():
        try:
            found = integrations.record_metrics(
                doctype, list({name for contact, name in rows})
            )
        except Exception:
            frappe.log_error(title=f"OneChat customer scores: {doctype}")
            continue
        for contact, name in rows:
            if name in found:
                out[contact] = found[name]
    return out


def top_value(stats):
    values = sorted(
        (
            flt(row.get("lifetime_value"))
            for row in stats
            if flt(row.get("lifetime_value"))
        ),
        reverse=True,
    )
    if len(values) < 10:
        return None
    return values[len(values) // 10 - 1]


def update(contacts, top=None):
    if not contacts:
        return 0
    now = now_datetime()
    today = getdate(nowdate())
    commerce = integrations.has_purchases()
    active = activity([row.name for row in contacts])
    bought = purchases(contacts) if commerce else {}
    for row in contacts:
        stats = bought.get(row.name, {})
        seen = active.get(row.name, {})
        values = {field: stats.get(field) for field in PURCHASE_FIELDS}
        values.update(
            lifetime_value=flt(values["lifetime_value"]),
            order_count=cint(values["order_count"]),
            outstanding_amount=flt(values["outstanding_amount"]),
            value_group=value_group(stats, top, today) if commerce else None,
            engagement_score=engagement(seen, now),
            last_reply_at=seen.get("last_reply_at"),
            scores_updated_at=now,
        )
        frappe.db.set_value(CONTACT, row.name, values, update_modified=False)
    return len(contacts)


def contact_rows(filters=None, start=0, size=BATCH):
    return frappe.get_all(
        CONTACT,
        filters=filters,
        fields=["name", "reference_doctype", "reference_docname"],
        order_by="name asc",
        limit_start=start,
        limit_page_length=size,
    )


def linked_rows():
    names = set(
        frappe.get_all(
            links.LINK, filters={"parenttype": CONTACT}, pluck="parent", distinct=True
        )
    )
    names.update(
        frappe.get_all(
            CONTACT, filters={"reference_docname": ["is", "set"]}, pluck="name"
        )
    )
    return (
        frappe.get_all(
            CONTACT,
            filters={"name": ["in", list(names)]},
            fields=["name", "reference_doctype", "reference_docname"],
        )
        if names
        else []
    )


def update_all():
    if not frappe.get_meta(CONTACT).has_field("value_group"):
        return
    top = (
        top_value(purchases(linked_rows()).values())
        if integrations.has_purchases()
        else None
    )
    frappe.cache().set_value(TOP_VALUE, top)
    start = 0
    while rows := contact_rows(start=start):
        update(rows, top)
        frappe.db.commit()  # nosemgrep: frappe-manual-commit - batch commit updated contact scores to avoid large transactions
        start += BATCH
    from onechat.inbox.segments import forget_overview

    forget_overview()


def update_contact(contact):
    update(contact_rows({"name": contact}, size=1), frappe.cache().get_value(TOP_VALUE))


def queue_update(contact):
    frappe.enqueue(
        update_contact,
        contact=contact,
        queue="short",
        deduplicate=True,
        job_id=f"onechat-scores-{contact}",
        enqueue_after_commit=True,
    )


@frappe.whitelist()
def refresh(contact: str):
    guard()
    check_visible(contact)
    update_contact(contact)
    return summary(contact)


@frappe.whitelist(methods=["POST"])
def refresh_all():
    require_admin()
    frappe.enqueue(
        update_all,
        queue="long",
        timeout=3600,
        deduplicate=True,
        job_id="onechat-scores-all",
    )
    return True


def summary(contact):
    row = frappe.db.get_value(
        CONTACT,
        contact,
        [
            "value_group",
            "engagement_score",
            "favourite_category",
            "lifetime_value",
            "order_count",
            "outstanding_amount",
            "last_purchase_on",
            "scores_updated_at",
        ],
        as_dict=True,
    )
    if not row:
        return {}
    group = GROUPS.get(row.value_group) or {}
    return {
        **row,
        "purchases": integrations.has_purchases(),
        "last_purchase_on": str(row.last_purchase_on) if row.last_purchase_on else None,
        "scores_updated_at": (
            str(get_datetime(row.scores_updated_at)) if row.scores_updated_at else None
        ),
        "group_theme": group.get("theme", "gray"),
        "group_hint": _(group["hint"]) if group.get("hint") else None,
    }
