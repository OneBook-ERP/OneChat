import json
from datetime import timedelta

import frappe
import requests
from frappe import _
from frappe.utils import cint, get_url, now_datetime

APP = "frappe_assistant_core"
ENDPOINT = "/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp"
CLIENT_NAME = "OneChat Assistant"
TOKEN_MINUTES = 15
TIMEOUT = 60
RESULT_LIMIT = 20000

READ = {
    "get_document",
    "list_documents",
    "search_documents",
    "search",
    "fetch",
    "report_list",
    "report_requirements",
    "generate_report",
    "get_doctype_info",
    "get_pending_approvals",
    "analyze_business_data",
    "extract_file_content",
    "list_user_dashboards",
}
CREATE = {"create_document", "create_dashboard", "create_dashboard_chart"}
WRITE = {"update_document", "submit_document", "run_workflow"}
BLOCKED = {"run_python_code", "run_database_query", "delete_document"}

READ_ONLY = "Read only"
READ_WRITE = "Read and write"
RIGHTS = ("read", "write", "create")
CHECKS = tuple(f"can_{right}" for right in RIGHTS)
SEPARATOR = "__"
REMOTE_CHECK_SECONDS = 600


class FacError(Exception):
    pass


def installed():
    return bool(servers(frappe.session.user))


def local_installed():
    return APP in frappe.get_installed_apps()


def remote_has_fac(row):
    key = f"onechat:assistant:remote:{row.key}"
    cached = frappe.cache().get_value(key)
    if cached is not None:
        return bool(cached)
    try:
        found = APP in (row.client().call("frappe.utils.change_log.get_versions") or {})
    except Exception:
        found = False
    frappe.cache().set_value(
        key, 1 if found else 0, expires_in_sec=REMOTE_CHECK_SECONDS
    )
    return found


def servers(user):
    out = []
    if local_installed():
        out.append(
            {
                "key": "local",
                "label": frappe.local.site,
                "url": get_url(ENDPOINT),
                "auth": lambda: f"Bearer {token(user)}",
                "reset": lambda: frappe.cache().delete_value(
                    f"onechat:assistant:token:{user}"
                ),
            }
        )
    from onechat.integrations import oauth

    for row in fac_sites():
        if per_agent():
            if not oauth.agent_signed_in(user, row.key):
                continue
            out.append(
                {
                    "key": row.key,
                    "label": row.label,
                    "url": f"{row.base_url()}{ENDPOINT}",
                    "auth": lambda row=row: agent_bearer(user, row),
                    "reset": lambda row=row: oauth.agent_token(user, row, force=True),
                }
            )
            continue
        out.append(
            {
                "key": row.key,
                "label": row.label,
                "url": f"{row.base_url()}{ENDPOINT}",
                "auth": lambda row=row: row.authorization(),
                "reset": lambda row=row: row.authorization(force=True),
            }
        )
    return out


def fac_sites():
    from onechat.integrations import connection

    return [
        row
        for row in connection.remote_sites()
        if row.uses_oauth() and remote_has_fac(row)
    ]


def per_agent():
    value = frappe.get_cached_doc("OneChat Settings").get("assistant_agent_signin")
    return value is None or bool(cint(value))


def agent_bearer(user, row):
    from onechat.integrations import oauth

    token = oauth.agent_token(user, row)
    if not token:
        raise FacError(
            _("Sign in to {0} again to use it in the Assistant.").format(row.label)
        )
    return f"Bearer {token}"


def sign_ins(user):
    if not per_agent():
        return []
    from onechat.integrations import oauth

    return [
        {
            "integration": row.key,
            "label": row.label,
            "signed_in_as": oauth.agent_signed_in(user, row.key) or "",
        }
        for row in fac_sites()
    ]


def base(name):
    return name.split(SEPARATOR, 1)[1] if SEPARATOR in name else name


def server_for(user, name):
    found = servers(user)
    if not found:
        raise FacError(missing_message(user))
    if SEPARATOR in name:
        key = name.split(SEPARATOR, 1)[0]
        for server in found:
            if server["key"] == key:
                return server
    return found[0]


def oauth_client():
    name = frappe.db.get_value("OAuth Client", {"app_name": CLIENT_NAME}, "name")
    if name:
        return name
    doc = frappe.get_doc(
        {
            "doctype": "OAuth Client",
            "app_name": CLIENT_NAME,
            "scopes": "all openid",
            "redirect_uris": get_url("/onechat"),
            "default_redirect_uri": get_url("/onechat"),
            "grant_type": "Authorization Code",
            "response_type": "Code",
            "skip_authorization": 1,
        }
    ).insert(ignore_permissions=True)
    return doc.name


def token(user):
    key = f"onechat:assistant:token:{user}"
    cached = frappe.cache().get_value(key)
    if cached:
        return cached
    value = frappe.generate_hash(length=40)
    frappe.get_doc(
        {
            "doctype": "OAuth Bearer Token",
            "client": oauth_client(),
            "user": user,
            "scopes": "all openid",
            "access_token": value,
            "refresh_token": frappe.generate_hash(length=40),
            "expires_in": TOKEN_MINUTES * 60,
            "expiration_time": now_datetime() + timedelta(minutes=TOKEN_MINUTES),
            "status": "Active",
        }
    ).insert(ignore_permissions=True)
    frappe.db.commit()  # nosemgrep: frappe-manual-commit - commit token immediately for external client access
    frappe.cache().set_value(key, value, expires_in_sec=(TOKEN_MINUTES - 2) * 60)
    return value


def cleanup_tokens():
    client = frappe.db.get_value("OAuth Client", {"app_name": CLIENT_NAME}, "name")
    if not client:
        return
    for name in frappe.get_all(
        "OAuth Bearer Token",
        filters={"client": client, "expiration_time": ["<", now_datetime()]},
        pluck="name",
        limit=500,
    ):
        frappe.delete_doc(
            "OAuth Bearer Token", name, ignore_permissions=True, force=True
        )


def rpc(server, method, params=None):
    payload = {
        "jsonrpc": "2.0",
        "id": frappe.generate_hash(length=8),
        "method": method,
        "params": params or {},
    }
    try:
        response = requests.post(
            server["url"],
            json=payload,
            headers={
                "Authorization": server["auth"](),
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            },
            timeout=TIMEOUT,
        )
    except requests.RequestException as error:
        raise FacError(
            _("Could not reach Frappe Assistant Core on {0}: {1}").format(
                server["label"], str(error)
            )
        ) from error
    if response.status_code in (401, 403):
        server["reset"]()
        raise FacError(
            _("Frappe Assistant Core on {0} refused the sign-in. Try again.").format(
                server["label"]
            )
        )
    if not response.ok:
        raise FacError(
            _("Frappe Assistant Core returned an error ({0}).").format(
                response.status_code
            )
        )
    body = parse(response)
    if body.get("error"):
        raise FacError(
            (body["error"] or {}).get("message") or _("Frappe Assistant Core error")
        )
    return body.get("result") or {}


def parse(response):
    if "text/event-stream" in (response.headers.get("Content-Type") or ""):
        for line in response.text.splitlines():
            if line.startswith("data:"):
                try:
                    return json.loads(line[5:].strip())
                except ValueError:
                    continue
        return {}
    try:
        return response.json()
    except ValueError:
        return {}


def access(user=None):
    from onechat.workspace.session import is_admin

    user = user or frappe.session.user
    meta = frappe.get_meta("OneChat Assistant Role")
    checks = [field for field in CHECKS if meta.has_field(field)]
    rows = frappe.get_all(
        "OneChat Assistant Role",
        filters={"parenttype": "OneChat Settings"},
        fields=["role", "access", *checks],
    )
    if not rows:
        return frozenset(RIGHTS) if is_admin(user) else frozenset({"read"})
    roles = set(frappe.get_roles(user))
    granted = set()
    for row in rows:
        if row.role in roles:
            granted |= rights_of(row, checks)
    if granted & {"write", "create"}:
        granted.add("read")
    return frozenset(granted) or None


def rights_of(row, checks):
    if checks:
        return {right for right in RIGHTS if cint(row.get(f"can_{right}"))}
    return set(RIGHTS) if row.access == READ_WRITE else {"read"}


def needed(name):
    name = base(name)
    if name in READ:
        return "read"
    if name in CREATE:
        return "create"
    return "write"


def allowed(name, level):
    if base(name) in BLOCKED or not level:
        return False
    return needed(name) in level


def needs_confirm(name):
    return base(name) not in READ


def missing_message(user):
    pending = [row["label"] for row in sign_ins(user) if not row["signed_in_as"]]
    if pending:
        return _("Sign in to {0} from the Assistant panel first.").format(
            ", ".join(pending)
        )
    return _(
        "Frappe Assistant Core is not installed on this site or on a connected site."
    )


def tools(user, level):
    found = servers(user)
    if not found:
        raise FacError(missing_message(user))
    many = len(found) > 1
    out = []
    for server in found:
        try:
            listed = rpc(server, "tools/list").get("tools") or []
        except FacError:
            if not many:
                raise
            frappe.log_error(title=f"OneChat assistant tools: {server['label']}")
            continue
        for tool in listed:
            name = tool.get("name")
            if not name or not allowed(name, level):
                continue
            schema = tool.get("inputSchema") or {}
            if schema.get("type") != "object":
                schema = {"type": "object", "properties": {}}
            description = tool.get("description") or name
            out.append(
                {
                    "name": f"{server['key']}{SEPARATOR}{name}" if many else name,
                    "description": (
                        f"[{server['label']}] {description}" if many else description
                    )[:1024],
                    "schema": schema,
                }
            )
    return out


def call(user, name, arguments, level):
    if not allowed(name, level):
        return _("This tool is not available to you."), True
    try:
        result = rpc(
            server_for(user, name),
            "tools/call",
            {"name": base(name), "arguments": arguments or {}},
        )
    except FacError as error:
        return str(error), True
    parts = [
        part.get("text") or ""
        for part in result.get("content") or []
        if part.get("type") == "text"
    ]
    text = "\n".join(parts).strip() or json.dumps(result, default=str)
    return text[:RESULT_LIMIT], bool(result.get("isError"))
