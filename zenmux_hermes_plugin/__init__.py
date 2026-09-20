"""ZenMux model-provider plugin for Hermes Agent."""

from __future__ import annotations

import json
import hmac
import html
import logging
import secrets
import urllib.request
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from hermes_cli.auth_oauth_pkce_plugin import (
    OAuthPKCEConfig,
    pkce_auth_handler,
    pkce_refresh_credential,
)
from providers import register_provider
from providers.base import ProviderProfile

_PLUGIN_DIR = Path(__file__).resolve().parent
_CONFIG_PATH = _PLUGIN_DIR / "zenmux.json"

_AUTHORIZE_URL = "https://zenmux.ai/oauth/authorize"
_TOKEN_URL = "https://zenmux.ai/oauth/token"
_API_BASE_URL = "https://zenmux.ai/api/v1"
_SCOPES = ("inference:invoke", "offline_access")
_MAX_CATALOG_BYTES = 4 * 1024 * 1024

logger = logging.getLogger(__name__)


def _completion_html(client_id: str) -> str:
    completion_url = (
        "https://zenmux.ai/platform/oauth-completed?"
        + urlencode({"clientId": client_id})
    )
    safe_url = html.escape(completion_url, quote=True)
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>ZenMux connected</title>"
        "<style>html,body,iframe{width:100%;height:100%;margin:0;border:0}"
        "body{overflow:hidden}iframe{display:block}</style></head>"
        f"<body><iframe src=\"{safe_url}\" title=\"ZenMux login completed\" "
        "referrerpolicy=\"no-referrer\"></iframe></body></html>"
    )


def _callback_handler(
    expected_path: str,
    *,
    expected_state: str,
    client_id: str,
) -> tuple[type[BaseHTTPRequestHandler], dict[str, Any]]:
    result: dict[str, Any] = {
        "code": None,
        "state": None,
        "error": None,
        "error_description": None,
    }

    class ZenMuxCallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path != expected_path:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Not found.")
                return

            params = parse_qs(parsed.query)
            for key in result:
                result[key] = params.get(key, [None])[0]
            valid = (
                not result["error"]
                and bool(result["code"])
                and hmac.compare_digest(str(result["state"] or ""), expected_state)
            )
            body = (
                _completion_html(client_id)
                if valid
                else (
                    "<!doctype html><meta charset=\"utf-8\">"
                    "<title>ZenMux authorization failed</title>"
                    "<h1>ZenMux authorization failed.</h1>"
                    "<p>Return to Hermes and start login again.</p>"
                )
            ).encode("utf-8")
            self.send_response(200 if valid else 400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; frame-src https://zenmux.ai; "
                "style-src 'unsafe-inline'",
            )
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            return

    return ZenMuxCallbackHandler, result


def _login(provider: str, oauth: OAuthPKCEConfig, *, open_browser: bool) -> dict[str, Any]:
    """Run Hermes' PKCE flow with ZenMux's client-aware completion iframe."""
    from hermes_cli.auth_device_flow import (
        _bind_loopback_callback_server,
        _can_open_graphical_browser,
        _pkce_code_challenge,
        _pkce_code_verifier,
        _print_loopback_ssh_hint,
        _serve_loopback_callback,
    )
    from hermes_cli.auth_oauth_pkce_plugin import _err, _post_token, validate_config

    validate_config(provider, oauth)
    path = (
        oauth.redirect_path
        if oauth.redirect_path.startswith("/")
        else f"/{oauth.redirect_path}"
    )
    state = secrets.token_urlsafe(32)
    handler, result = _callback_handler(
        path,
        expected_state=state,
        client_id=oauth.client_id,
    )
    error = lambda message, code: _err(provider, message, code)  # noqa: E731
    server = _bind_loopback_callback_server(
        "127.0.0.1",
        int(oauth.redirect_port),
        handler,
        err=error,
        bind_failed_code="oauth_callback_bind_failed",
    )
    redirect_uri = f"http://127.0.0.1:{server.server_address[1]}{path}"
    verifier = _pkce_code_verifier()
    params = {
        **oauth.extra_authorize_params,
        "client_id": oauth.client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": _pkce_code_challenge(verifier),
        "code_challenge_method": "S256",
    }
    if oauth.scopes:
        params["scope"] = " ".join(oauth.scopes)
    if oauth.audience:
        params["audience"] = oauth.audience
    authorize_url = (
        f"{oauth.authorize_url}"
        f"{'&' if urlparse(oauth.authorize_url).query else '?'}"
        f"{urlencode(params)}"
    )

    print(
        f"\nOpen this URL to authorize Hermes with {oauth.label or provider}:\n"
        f"  {authorize_url}\n"
    )
    print(
        f"Waiting for callback on {redirect_uri} "
        f"(timeout {int(oauth.timeout_seconds)}s, Ctrl+C to cancel)..."
    )
    _print_loopback_ssh_hint(redirect_uri)
    if open_browser and _can_open_graphical_browser():
        try:
            webbrowser.open(authorize_url)
        except Exception:
            print("Could not open the browser automatically; use the URL above.")
    try:
        callback = _serve_loopback_callback(
            server,
            result,
            timeout_seconds=oauth.timeout_seconds,
            err=error,
            timeout_code="oauth_callback_timeout",
        )
    except KeyboardInterrupt:
        print("\nLogin cancelled.")
        raise SystemExit(130)

    if callback.get("error"):
        raise error(
            "authorization failed: "
            f"{callback.get('error_description') or callback['error']}",
            "oauth_authorization_denied",
        )
    if not hmac.compare_digest(str(callback.get("state") or ""), state):
        raise error(
            "callback state mismatch — the redirect did not come from this login. "
            "Aborting.",
            "oauth_state_mismatch",
        )
    code = str(callback.get("code") or "").strip()
    if not code:
        raise error("callback carried no authorization code.", "oauth_no_code")
    return _post_token(
        provider,
        oauth,
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
        },
        code="oauth_token_exchange_failed",
    )


def _auth_handler(oauth: OAuthPKCEConfig):
    standard_handler = pkce_auth_handler(oauth)

    def handler(action: str, args: Any) -> bool:
        if action != "add":
            return standard_handler(action, args)
        from agent.credential_pool import AUTH_TYPE_OAUTH, PooledCredential, load_pool

        provider = str(getattr(args, "provider", "") or "").strip().lower()
        tokens = _login(
            provider,
            oauth,
            open_browser=not getattr(args, "no_browser", False),
        )
        entry = load_pool(provider).add_entry(
            PooledCredential(
                provider=provider,
                id=uuid.uuid4().hex[:6],
                label=oauth.label or provider,
                auth_type=AUTH_TYPE_OAUTH,
                priority=0,
                source="manual:loopback_pkce",
                base_url=_API_BASE_URL,
                **tokens,
                extra={
                    "oauth_pkce": {
                        "client_id": oauth.client_id,
                        "scope": " ".join(oauth.scopes),
                    }
                },
            )
        )
        print(
            f"Signed in to {oauth.label or provider}; "
            f"credential {entry.id} added to the pool."
        )
        return True

    return handler


def _client_id(config_path: Path = _CONFIG_PATH) -> str:
    """Read the non-secret public OAuth client ID from the plugin config."""
    try:
        value: Any = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(value, dict):
        return ""
    client_id = value.get("client_id")
    return client_id.strip() if isinstance(client_id, str) else ""


def model_ids_from_payload(payload: Any) -> list[str]:
    """Return unique text-output model IDs from a ZenMux catalog payload."""
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise ValueError("ZenMux model response does not contain a data array")
    result: list[str] = []
    seen: set[str] = set()
    for item in payload["data"]:
        if not isinstance(item, dict):
            continue
        model_id = item.get("id")
        if not isinstance(model_id, str) or not model_id.strip():
            continue
        outputs = item.get("output_modalities")
        if isinstance(outputs, list) and "text" not in outputs:
            continue
        normalized = model_id.strip()
        if normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


class ZenMuxProfile(ProviderProfile):
    """Provider profile with ZenMux catalog modality filtering."""

    def fetch_models(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 8.0,
    ) -> list[str] | None:
        caller_base = (base_url or "").strip()
        custom_base = bool(caller_base) and (
            caller_base.rstrip("/") != self.base_url.rstrip("/")
        )
        url = (
            f"{caller_base.rstrip('/')}/models"
            if custom_base
            else self.models_url
        )
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "hermes-cli/zenmux-plugin",
                **(
                    {"Authorization": f"Bearer {api_key}"}
                    if api_key
                    else {}
                ),
            },
        )
        try:
            from hermes_cli.urllib_security import open_credentialed_url

            with open_credentialed_url(request, timeout=timeout) as response:
                body = response.read(_MAX_CATALOG_BYTES + 1)
            if len(body) > _MAX_CATALOG_BYTES:
                raise ValueError("ZenMux model response exceeds 4 MiB")
            return model_ids_from_payload(json.loads(body.decode("utf-8")))
        except Exception as exc:
            logger.debug("fetch_models(%s): %s", self.name, exc)
            return None


def build_profile(config_path: Path = _CONFIG_PATH) -> ProviderProfile:
    """Build the provider profile without performing network or auth I/O."""
    oauth = OAuthPKCEConfig(
        client_id=_client_id(config_path),
        authorize_url=_AUTHORIZE_URL,
        token_url=_TOKEN_URL,
        scopes=_SCOPES,
        redirect_port=0,
        redirect_path="/callback",
        timeout_seconds=600,
        label="ZenMux",
    )
    return ZenMuxProfile(
        name="zenmux",
        aliases=("zenmux-ai",),
        display_name="ZenMux",
        description="Access leading AI models through ZenMux",
        signup_url="https://zenmux.ai",
        api_mode="chat_completions",
        auth_type="oauth_external",
        base_url=_API_BASE_URL,
        models_url=f"{_API_BASE_URL}/models",
        auth_handler=_auth_handler(oauth),
        refresh_credential=pkce_refresh_credential(oauth),
        supports_vision=True,
        fallback_models=(
            "anthropic/claude-sonnet-4.5",
            "openai/gpt-5.2",
            "deepseek/deepseek-v3.2",
        ),
    )


def register() -> None:
    """Register the ZenMux model provider with Hermes Agent."""
    register_provider(build_profile())
