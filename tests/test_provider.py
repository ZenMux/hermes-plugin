from __future__ import annotations

import json
import urllib.request
from argparse import Namespace
from types import SimpleNamespace

import zenmux_hermes_plugin


def test_profile_uses_hermes_declarative_oauth_hooks(tmp_path):
    module = zenmux_hermes_plugin
    config = tmp_path / "zenmux.json"
    config.write_text(json.dumps({"client_id": "zpc_Hermes_test"}), encoding="utf-8")

    profile = module.build_profile(config)

    assert profile.name == "zenmux"
    assert profile.auth_type == "oauth_external"
    assert profile.api_mode == "chat_completions"
    assert profile.base_url == "https://zenmux.ai/api/v1"
    assert profile.models_url == "https://zenmux.ai/api/v1/models"
    assert callable(profile.auth_handler)
    assert callable(profile.refresh_credential)
    assert profile.fallback_models
    if hasattr(profile, "model_listing_authoritative"):
        assert profile.model_listing_authoritative is False


def test_missing_client_id_does_not_break_provider_discovery(tmp_path):
    module = zenmux_hermes_plugin
    config = tmp_path / "zenmux.json"
    config.write_text('{"client_id": ""}\n', encoding="utf-8")

    profile = module.build_profile(config)

    assert profile.name == "zenmux"
    assert callable(profile.auth_handler)


def test_catalog_keeps_only_unique_text_output_models():
    module = zenmux_hermes_plugin

    models = module.model_ids_from_payload(
        {
            "data": [
                {"id": "vendor/text", "output_modalities": ["text"]},
                {"id": "vendor/image", "output_modalities": ["image"]},
                {"id": "vendor/legacy"},
                {"id": " vendor/text ", "output_modalities": ["text"]},
                {"id": ""},
                None,
            ]
        }
    )

    assert models == ["vendor/text", "vendor/legacy"]


def test_checked_in_config_contains_a_public_client_id():
    module = zenmux_hermes_plugin

    assert module._client_id().startswith("zpc_")


def test_success_callback_embeds_client_aware_completion_page():
    module = zenmux_hermes_plugin

    body = module._completion_html("zpc_Hermes_test")

    assert (
        'src="https://zenmux.ai/platform/oauth-completed?'
        'clientId=zpc_Hermes_test"' in body
    )
    assert "html,body,iframe{width:100%;height:100%;margin:0;border:0}" in body


def test_callback_rejects_wrong_state_without_rendering_completion_iframe():
    module = zenmux_hermes_plugin
    handler, result = module._callback_handler(
        "/callback",
        expected_state="expected",
        client_id="zpc_Hermes_test",
    )
    from http.server import HTTPServer
    from threading import Thread

    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.handle_request)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/callback"
        with urllib.request.urlopen(f"{url}?code=test&state=wrong") as response:
            response.read()
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8")
        assert error.code == 400
        assert "<iframe" not in body
    finally:
        thread.join(timeout=2)
        server.server_close()

    assert result["state"] == "wrong"


def test_auth_handler_persists_the_zenmux_runtime_endpoint(monkeypatch):
    module = zenmux_hermes_plugin
    oauth = module.OAuthPKCEConfig(
        client_id="zpc_Hermes_test",
        authorize_url="https://zenmux.ai/oauth/authorize",
        token_url="https://zenmux.ai/oauth/token",
    )
    captured = []
    entry = SimpleNamespace(id="test-id")
    pool = SimpleNamespace(add_entry=lambda value: captured.append(value) or entry)
    monkeypatch.setattr(
        module,
        "_login",
        lambda *_args, **_kwargs: {
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_at_ms": 123,
            "last_refresh": "now",
        },
    )
    import agent.credential_pool

    monkeypatch.setattr(agent.credential_pool, "load_pool", lambda _provider: pool)

    assert module._auth_handler(oauth)("add", Namespace(provider="zenmux", no_browser=True))
    assert captured[0].base_url == "https://zenmux.ai/api/v1"
