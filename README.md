# ZenMux for Hermes Agent

Use [ZenMux](https://zenmux.ai) models in
[Hermes Agent](https://github.com/NousResearch/hermes-agent) with browser OAuth.
The plugin provides:

- OAuth 2.0 Authorization Code + PKCE login
- access/refresh-token storage in Hermes' credential pool
- serialized refresh-token rotation
- a live ZenMux model catalog in `hermes model`
- direct use of full ZenMux model slugs
- OpenAI-compatible chat-completions transport

## Requirements

- Hermes Agent with the declarative OAuth PKCE plugin API (main at or after
  `3e67877e1b`).
- Python 3.11 or newer when installing from PyPI.
- A browser for the initial ZenMux authorization.

The package includes ZenMux's dedicated public OAuth client for Hermes. No
client secret is bundled or required.

## Installation

### Option A: install from GitHub (recommended)

```bash
hermes plugins install ZenMux/hermes-plugin --enable
hermes gateway restart
```

For a reproducible installation, pin an immutable commit shown on the latest
release page:

```bash
hermes plugins install ZenMux/hermes-plugin --ref <40-character-commit> --enable
```

If another process manager owns the gateway, restart it there instead:

```bash
pm2 restart hermes-gateway --update-env
```

### Option B: install from PyPI

Install into the **same Python environment as Hermes**:

```bash
~/.hermes/hermes-agent/venv/bin/python -m pip install zenmux-hermes-plugin
hermes plugins enable zenmux
hermes gateway restart
```

A system-wide Hermes installation may instead use:

```bash
python3 -m pip install zenmux-hermes-plugin
hermes plugins enable zenmux
```

### Option C: install as a filesystem provider

```bash
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
mkdir -p "$HERMES_HOME/plugins/model-providers"
git clone https://github.com/ZenMux/hermes-plugin.git \
  "$HERMES_HOME/plugins/model-providers/zenmux"
```

Restart Hermes after installation.

## Sign in to ZenMux

```bash
hermes auth add zenmux
hermes auth status zenmux
```

Hermes opens ZenMux. Select an account and billing method, then approve access.
Useful commands:

```bash
hermes auth list zenmux
hermes auth refresh zenmux
hermes auth logout zenmux
```

Access and refresh tokens are stored by Hermes in its credential pool, not in
the plugin. `zenmux.json` contains only the public OAuth client ID.

## Remote and headless hosts

The callback is a temporary loopback URL such as:

```text
http://127.0.0.1:54321/callback
```

When Hermes is remote, forward the exact printed port:

```bash
# Local terminal
ssh -N -L 54321:127.0.0.1:54321 user@remote-host

# Remote terminal
hermes auth add zenmux --no-browser
```

Use the latest login URL and port. Version 0.1.1+ waits ten minutes. For managed
containers without SSH forwarding, complete authorization in a temporary local
Hermes home and securely merge only `credential_pool.zenmux` into the remote
`auth.json`. Never paste OAuth tokens into chat or overwrite unrelated provider
credentials.

## Select a model

Interactive picker:

```bash
hermes model
```

Direct full slug:

```bash
hermes --provider zenmux -m google/gemini-2.5-flash-lite
hermes --provider zenmux -m anthropic/claude-sonnet-4.5
```

Messaging command:

```text
/model z-ai/glm-5.3-flashx
```

`zenmux` is the provider, not a model prefix. Use `z-ai/glm-5.3-flashx`, not
`zenmux/glm-5.3-flashx`.

### Models absent from the catalog

The live `/api/v1/models` result powers the picker and typo suggestions; it is
not intended as a hard allowlist. ZenMux can accept account-, rollout-, or
route-specific slugs absent from the public catalog.

Hermes builds with `ProviderProfile.model_listing_authoritative` allow this
plugin to pass an unlisted slug through with a warning. Older Hermes builds
reject it before sending the request; update Hermes first. ZenMux remains the
final authority and will reject an invalid or inaccessible slug.

## Configure ZenMux as the default

```bash
hermes config set model.provider zenmux
hermes config set model.default google/gemini-2.5-flash-lite
hermes config set model.base_url https://zenmux.ai/api/v1
hermes config set model.api_mode chat_completions
```

Verify:

```bash
hermes -z "Reply with exactly: OK" --safe-mode
```

## Catalog behavior

The plugin reads `https://zenmux.ai/api/v1/models`. It:

- keeps text-output models
- filters image/video-only generation models from the chat picker
- preserves full `vendor/model` IDs
- does not embed a generated catalog snapshot
- retains a small fallback list for temporary catalog failures

## Update

GitHub install:

```bash
hermes plugins install ZenMux/hermes-plugin --force --enable
hermes gateway restart
```

PyPI install:

```bash
~/.hermes/hermes-agent/venv/bin/python -m pip install --upgrade zenmux-hermes-plugin
hermes gateway restart
```

## Uninstall

GitHub install:

```bash
hermes auth logout zenmux
hermes plugins disable zenmux
rm -rf "${HERMES_HOME:-$HOME/.hermes}/plugins/zenmux"
```

PyPI install:

```bash
hermes auth logout zenmux
hermes plugins disable zenmux
~/.hermes/hermes-agent/venv/bin/python -m pip uninstall zenmux-hermes-plugin
```

## Troubleshooting

### `Unknown provider 'zenmux'`

```bash
hermes plugins list
hermes plugins enable zenmux
hermes gateway restart
```

### Authorization timeout

Start a fresh login and use its new URL/port. On remote hosts, forward that
port. Authorization codes from expired attempts cannot be reused.

### Logged in, but inference reports no endpoint

Update the plugin and sign in again. Current credential rows include
`base_url=https://zenmux.ai/api/v1`; early development builds did not.

### Model rejected as absent from the listing

Check the full slug first. For intentionally unlisted slugs, update Hermes to a
build supporting `model_listing_authoritative`, then update this plugin.

### Proxy environments

Use standard `HTTP_PROXY`/`HTTPS_PROXY`. If a proxy terminates TLS, trust its CA
using `SSL_CERT_FILE`/`REQUESTS_CA_BUNDLE`. Never disable TLS verification
globally.

## Development

```bash
pytest -q tests
ruff check .
python -m build
twine check dist/*
```

Use another registered public client only for development:

```bash
python3 configure.py zpc_YOUR_DEVELOPMENT_CLIENT_ID
```

## Security

- HTTPS authorization/token endpoints
- callback listener bound only to `127.0.0.1`
- constant-time OAuth state comparison
- S256 PKCE
- no client secret
- no token/code/state/verifier logging
- serialized refresh-token rotation through Hermes' credential lock
- token endpoint host allowlist validation

## License

MIT
