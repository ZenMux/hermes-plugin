# ZenMux for Hermes Agent

An out-of-tree Hermes model-provider plugin that connects ZenMux using OAuth
2.0 Authorization Code with PKCE. Hermes owns the browser callback, credential
pool, proactive refresh, and refresh-token serialization.

## Requirements

- A Hermes Agent build containing the declarative OAuth PKCE plugin API
  (NousResearch/hermes-agent main at or after `3e67877e1b`).
- A **dedicated** ZenMux public OAuth client for Hermes. Do not reuse a client
  registered for DSH, Codex, or another application.
- Allowed scope: `inference:invoke offline_access`.
- Allowed loopback redirect URI: `http://127.0.0.1:*` (Hermes chooses an
  ephemeral port).

## Install from a checkout

### PyPI

Install the package into the same Python environment as Hermes, then explicitly
enable its entry point:

```bash
python3 -m pip install zenmux-hermes-plugin
hermes plugins enable zenmux
```

Restart an already-running Hermes process after installation.

### Git checkout

```bash
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
mkdir -p "$HERMES_HOME/plugins/model-providers"
git clone https://github.com/ZenMux/hermes-plugin.git \
  "$HERMES_HOME/plugins/model-providers/zenmux"
cd "$HERMES_HOME/plugins/model-providers/zenmux"
```

The repository already contains the dedicated Hermes public client ID. The
`configure.py` command is only needed for development against another
registered client:

```bash
python3 configure.py zpc_YOUR_DEVELOPMENT_CLIENT_ID
```

Restart an already-running Hermes process after installing or updating a
checkout. Then authenticate and select a model:

```bash
hermes auth add zenmux
hermes auth status zenmux
hermes model
```

`hermes auth refresh zenmux` rotates the access and refresh tokens.
`hermes auth logout zenmux` removes the ZenMux credential rows.

After a valid callback, the loopback page embeds ZenMux's client-aware
completion page in a full-screen iframe. A callback with an invalid OAuth
`state` never renders the success iframe.

The public client ID is stored in `zenmux.json`. OAuth access and refresh
tokens are not stored by this plugin; Hermes keeps them in its credential
pool.

## Current transport

The first release uses ZenMux's OpenAI-compatible endpoint:

```text
https://zenmux.ai/api/v1
```

The live model picker reads `https://zenmux.ai/api/v1/models` with the pooled
OAuth access token. No static model list is embedded in the plugin.
