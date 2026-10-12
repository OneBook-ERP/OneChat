import base64
import hashlib
from urllib.parse import urlencode

import frappe
import requests
from frappe import _
from frappe.utils import add_to_date, get_datetime, get_url, now_datetime
from frappe.utils.password import get_decrypted_password

from onechat.api_types import JSON
from onechat.integrations import connection
from onechat.workspace.session import require_admin, require_app_user

AUTHORIZE = "/api/method/frappe.integrations.oauth2.authorize"
TOKEN = "/api/method/frappe.integrations.oauth2.get_token"
REVOKE = "/api/method/frappe.integrations.oauth2.revoke_token"
CALLBACK = "onechat.integrations.oauth.callback"
SCOPE = "all openid"
STATE_TTL = 600
EARLY_SECONDS = 60
AGENT_TOKEN = "OneChat Agent Token"


def redirect_uri():
    return get_url(f"/api/method/{CALLBACK}")


def secret(row, field):
    return get_decrypted_password(
        connection.CONNECTION, row.key, field, raise_exception=False
    )


def challenge(verifier):
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


@frappe.whitelist(methods=["POST"])
def start(integration: str, url: str, client_id: str, client_secret: str | None = None):
    require_admin()
    from onechat.integrations.remote_setup import clean_url

    row = connection.site(integration)
    client_id = (client_id or "").strip()
    if not client_id:
        frappe.throw(
            _("Enter the client ID of the OAuth client you created on {0}.").format(
                row.label
            )
        )

    values = {
        "mode": connection.ANOTHER_SITE,
        "auth_method": connection.OAUTH,
        "url": clean_url(url, row.label),
        "client_id": client_id,
    }
    if client_secret:
        values["client_secret"] = client_secret.strip()
    row.update(values)
    row.clear_cache()

    state = frappe.generate_hash(length=32)
    verifier = frappe.generate_hash(length=64)
    frappe.cache().set_value(
        f"onechat:oauth:{state}",
        {"integration": integration, "verifier": verifier, "user": frappe.session.user},
        expires_in_sec=STATE_TTL,
    )
    return authorize_url(row, client_id, state, verifier)


def back_to_app(integration, error=None):
    query = {"settings": "integrations", "integration": integration or ""}
    if error:
        query["oauth_error"] = str(error)[:300]
    else:
        query["connected"] = integration
    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = f"/onechat?{urlencode(query)}"


def authorize_url(row, client_id, state, verifier):
    query = urlencode(
        {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri(),
            "scope": SCOPE,
            "state": state,
            "code_challenge": challenge(verifier),
            "code_challenge_method": "S256",
        }
    )
    return f"{row.base_url()}{AUTHORIZE}?{query}"


@frappe.whitelist(methods=["POST"])
def agent_start(integration: str, next_path: JSON = None):
    require_app_user()
    row = connection.site(integration)
    client_id = row.row().get("client_id")
    if not row.is_remote() or not row.uses_oauth() or not client_id:
        frappe.throw(
            _("An admin needs to connect {0} with Sign in (OAuth) first.").format(
                row.label
            )
        )

    state = frappe.generate_hash(length=32)
    verifier = frappe.generate_hash(length=64)
    back = (
        next_path
        if isinstance(next_path, str) and next_path.startswith("/onechat")
        else "/onechat"
    )
    frappe.cache().set_value(
        f"onechat:oauth:{state}",
        {
            "integration": integration,
            "verifier": verifier,
            "user": frappe.session.user,
            "agent": True,
            "next": back,
        },
        expires_in_sec=STATE_TTL,
    )
    return authorize_url(row, client_id, state, verifier)


def back_to_agent(saved, error=None):
    query = (
        {"assistant_error": str(error)[:300]}
        if error
        else {"assistant_signed_in": saved.get("integration") or ""}
    )
    path = saved.get("next") or "/onechat"
    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = (
        f"{path}{'&' if '?' in path else '?'}{urlencode(query)}"
    )


def agent_callback(saved, code, error, error_description):
    if error or not code:
        return back_to_agent(
            saved, error_description or error or _("Sign-in was cancelled.")
        )
    row = connection.site(saved["integration"])
    try:
        tokens = exchange(
            row,
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri(),
                "code_verifier": saved["verifier"],
            },
        )
        remote_user = whoami(row, tokens["access_token"])
        store_agent(saved["user"], row, tokens, remote_user)
    except Exception as err:
        frappe.db.rollback()
        frappe.log_error(title=f"OneChat {row.label} agent sign-in")
        return back_to_agent(saved, err)
    return back_to_agent(saved)


def whoami(row, token):
    response = requests.get(
        f"{row.base_url()}/api/method/frappe.auth.get_logged_user",
        headers={"Authorization": f"Bearer {token}"},
        timeout=connection.TIMEOUT,
    )
    if not response.ok:
        raise connection.RemoteError(
            _("{0} did not accept the new sign-in ({1}).").format(
                row.label, response.status_code
            )
        )
    return (response.json() or {}).get("message") or ""


def agent_doc(user, integration):
    name = frappe.db.get_value(AGENT_TOKEN, {"user": user, "integration": integration})
    return frappe.get_doc(AGENT_TOKEN, name) if name else None


def store_agent(user, row, tokens, remote_user=None):
    doc = agent_doc(user, row.key) or frappe.new_doc(AGENT_TOKEN)
    doc.update(
        {
            "user": user,
            "integration": row.key,
            "access_token": tokens["access_token"],
            "expires_at": add_to_date(
                now_datetime(), seconds=int(tokens.get("expires_in") or 3600)
            ),
        }
    )
    if tokens.get("refresh_token"):
        doc.refresh_token = tokens["refresh_token"]
    if remote_user:
        doc.remote_user = remote_user
    doc.save(ignore_permissions=True)
    frappe.db.commit()  # nosemgrep: frappe-manual-commit - persist stored agent oauth token credentials


def agent_token(user, row, force=False):
    doc = agent_doc(user, row.key)
    if not doc:
        return None
    token = doc.get_password("access_token", raise_exception=False)
    if (
        token
        and not force
        and doc.expires_at
        and get_datetime(doc.expires_at)
        > add_to_date(now_datetime(), seconds=EARLY_SECONDS)
    ):
        return token
    refresh_token = doc.get_password("refresh_token", raise_exception=False)
    if not refresh_token:
        frappe.delete_doc(AGENT_TOKEN, doc.name, ignore_permissions=True, force=True)
        return None
    try:
        tokens = exchange(
            row, {"grant_type": "refresh_token", "refresh_token": refresh_token}
        )
    except connection.RemoteError as error:
        if not error.transient:
            frappe.delete_doc(
                AGENT_TOKEN, doc.name, ignore_permissions=True, force=True
            )
            frappe.db.commit()  # nosemgrep: frappe-manual-commit - persist agent token cleanup on invalid refresh
            return None
        raise
    store_agent(user, row, tokens)
    return tokens["access_token"]


def agent_signed_in(user, integration):
    return frappe.db.get_value(
        AGENT_TOKEN, {"user": user, "integration": integration}, "remote_user"
    )


@frappe.whitelist(methods=["POST"])
def agent_sign_out(integration: str):
    require_app_user()
    doc = agent_doc(frappe.session.user, integration)
    if not doc:
        return
    token = doc.get_password(
        "refresh_token", raise_exception=False
    ) or doc.get_password("access_token", raise_exception=False)
    if token:
        try:
            requests.post(
                f"{connection.site(integration).base_url()}{REVOKE}",
                data={"token": token},
                timeout=connection.TIMEOUT,
            )
        except requests.RequestException:
            pass
    frappe.delete_doc(AGENT_TOKEN, doc.name, ignore_permissions=True, force=True)


@frappe.whitelist(methods=["GET"])
def callback(
    code: str | None = None,
    state: JSON = None,
    error: str | None = None,
    error_description: str | None = None,
):
    require_app_user()
    saved = frappe.cache().get_value(f"onechat:oauth:{state}") if state else None
    frappe.cache().delete_value(f"onechat:oauth:{state}")
    if saved and saved.get("agent") and saved.get("user") == frappe.session.user:
        return agent_callback(saved, code, error, error_description)

    require_admin()
    integration = (saved or {}).get("integration")

    if not saved or saved.get("user") != frappe.session.user:
        return back_to_app(
            integration,
            _("The sign-in link expired. Start again from Settings → Integrations."),
        )
    if error or not code:
        return back_to_app(
            integration, error_description or error or _("Sign-in was cancelled.")
        )

    row = connection.site(integration)
    try:
        tokens = exchange(
            row,
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri(),
                "code_verifier": saved["verifier"],
            },
        )
        store(row, tokens)
        from onechat.integrations.remote_setup import check, enable, sync

        result = check(row)
        row.update({"oauth_user": result.get("user")})
        sync(integration)
        enable(integration)
    except Exception as err:
        frappe.db.rollback()
        frappe.log_error(title=f"OneChat {row.label} OAuth")
        return back_to_app(integration, err)

    return back_to_app(integration)


def exchange(row, data):
    data = {**data, "client_id": row.row().get("client_id")}
    client_secret = secret(row, "client_secret")
    if client_secret:
        data["client_secret"] = client_secret
    try:
        response = requests.post(
            f"{row.base_url()}{TOKEN}", data=data, timeout=connection.TIMEOUT
        )
    except requests.RequestException as error:
        raise connection.RemoteError(
            _("Could not reach {0} at {1}: {2}").format(
                row.label, row.base_url(), str(error)
            ),
            transient=True,
        ) from error

    try:
        body = response.json()
    except ValueError:
        body = {}
    if not response.ok or not body.get("access_token"):
        message = (
            body.get("error_description")
            or body.get("error")
            or connection.error_text(body)
        )
        raise connection.RemoteError(
            message
            or _("{0} did not accept the sign-in ({1}).").format(
                row.label, response.status_code
            ),
            status=response.status_code,
        )
    return body


def store(row, tokens):
    values = {
        "access_token": tokens["access_token"],
        "token_expires_at": add_to_date(
            now_datetime(), seconds=int(tokens.get("expires_in") or 3600)
        ),
    }
    if tokens.get("refresh_token"):
        values["refresh_token"] = tokens["refresh_token"]
    row.update(values)
    frappe.db.commit()  # nosemgrep: frappe-manual-commit - persist oauth tokens for integration connection


def access_token(row, force=False):
    token = secret(row, "access_token")
    expires = row.row().get("token_expires_at")
    fresh = (
        token
        and expires
        and get_datetime(expires) > add_to_date(now_datetime(), seconds=EARLY_SECONDS)
    )
    if fresh and not force:
        return token
    return refresh(row)


def refresh(row):
    frappe.db.get_value(connection.CONNECTION, row.key, "name", for_update=True)
    refresh_token = secret(row, "refresh_token")
    if not refresh_token:
        raise connection.RemoteError(
            _("Sign in to {0} again from Settings → Integrations.").format(row.label),
            status=401,
        )
    try:
        tokens = exchange(
            row, {"grant_type": "refresh_token", "refresh_token": refresh_token}
        )
    except connection.RemoteError as error:
        if not error.transient:
            row.record_status(
                _(
                    "Signed out: {0}. Sign in again from Settings → Integrations."
                ).format(str(error)),
                False,
            )
            frappe.db.commit()  # nosemgrep: frappe-manual-commit - persist connection error status on refresh failure
        raise
    store(row, tokens)
    return tokens["access_token"]


def revoke(row):
    token = secret(row, "refresh_token") or secret(row, "access_token")
    if token:
        try:
            requests.post(
                f"{row.base_url()}{REVOKE}",
                data={"token": token},
                timeout=connection.TIMEOUT,
            )
        except requests.RequestException:
            pass
    row.update(
        {
            "access_token": "",
            "refresh_token": "",
            "token_expires_at": None,
            "oauth_user": "",
        }
    )
