# ZenMux for Hermes Agent

[English](README.md) | [简体中文](README.zh.md)

通过浏览器 OAuth，在
[Hermes Agent](https://github.com/NousResearch/hermes-agent) 中使用
[ZenMux](https://zenmux.ai) 模型。本插件提供：

- OAuth 2.0 Authorization Code + PKCE 登录
- 通过 Hermes 凭据池保存 access token 和 refresh token
- 串行化 refresh token 轮换
- 在 `hermes model` 中展示实时 ZenMux 模型目录
- 直接使用完整 ZenMux 模型 slug
- OpenAI 兼容的 Chat Completions 协议

## 环境要求

- Hermes Agent 已包含声明式 OAuth PKCE 插件 API（main 分支至少包含
  `3e67877e1b`）。
- 通过 PyPI 安装时需要 Python 3.11 或更高版本。
- 首次授权需要浏览器。

包内已经包含 ZenMux 为 Hermes 注册的专用 public OAuth client，不需要也不会携带
client secret。

## 安装

### 方式一：从 GitHub 安装（推荐）

```bash
hermes plugins install ZenMux/hermes-plugin --enable
hermes gateway restart
```

如需可复现安装，可使用最新 Release 页面展示的完整 40 位 commit：

```bash
hermes plugins install ZenMux/hermes-plugin \
  --ref <40-character-commit> \
  --enable
```

如果 Gateway 由其他进程管理器托管，请在那里重启。例如：

```bash
pm2 restart hermes-gateway --update-env
```

### 方式二：从 PyPI 安装

必须安装到与 Hermes **相同的 Python 环境**：

```bash
~/.hermes/hermes-agent/venv/bin/python -m pip install zenmux-hermes-plugin
hermes plugins enable zenmux
hermes gateway restart
```

如果 Hermes 是系统级安装，也可以使用：

```bash
python3 -m pip install zenmux-hermes-plugin
hermes plugins enable zenmux
```

### 方式三：作为文件系统 Provider 安装

```bash
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
mkdir -p "$HERMES_HOME/plugins/model-providers"
git clone https://github.com/ZenMux/hermes-plugin.git \
  "$HERMES_HOME/plugins/model-providers/zenmux"
```

安装完成后重启 Hermes。

## 登录 ZenMux

```bash
hermes auth add zenmux
hermes auth status zenmux
```

Hermes 会打开 ZenMux 授权页。选择账户和计费方式，然后批准授权。

常用认证命令：

```bash
hermes auth list zenmux
hermes auth refresh zenmux
hermes auth logout zenmux
```

access token 和 refresh token 由 Hermes 保存在凭据池中，不保存在插件目录。
`zenmux.json` 只包含 public OAuth client ID。

## 远程与无界面服务器

OAuth 回调使用临时 loopback 地址，例如：

```text
http://127.0.0.1:54321/callback
```

Hermes 运行在远程服务器时，请转发登录命令实际打印的端口：

```bash
# 本机终端
ssh -N -L 54321:127.0.0.1:54321 user@remote-host

# 远程终端
hermes auth add zenmux --no-browser
```

必须使用最新一次登录显示的 URL 和端口。`0.1.1` 及以上版本会等待最多 10 分钟。

对于没有 SSH 端口转发能力的托管容器，可以在临时本地 `HERMES_HOME` 中完成授权，
再安全地只合并 `credential_pool.zenmux` 到远程 `auth.json`。不要把 OAuth token
粘贴到聊天中，也不要用整个本地 `auth.json` 覆盖远程的其他 provider 凭据。

## 选择模型

打开交互式模型选择器：

```bash
hermes model
```

直接指定完整 slug：

```bash
hermes --provider zenmux -m google/gemini-2.5-flash-lite
hermes --provider zenmux -m anthropic/claude-sonnet-4.5
```

在聊天或消息机器人中：

```text
/model z-ai/glm-5.3-flashx
```

`zenmux` 是 provider 名，不是模型 slug 前缀。正确写法是：

```text
z-ai/glm-5.3-flashx
```

而不是：

```text
zenmux/glm-5.3-flashx
```

### 使用模型目录之外的 slug

实时 `/api/v1/models` 用于模型选择器和拼写建议，不应该成为硬白名单。ZenMux
可能接受尚未出现在公开目录中的账户专属、灰度或特殊路由模型 slug。

当 Hermes 包含 `ProviderProfile.model_listing_authoritative` 能力时，本插件允许目录外
slug 通过，并显示提示。旧版 Hermes 会在请求发送前拒绝目录外 slug，需要先更新
Hermes。最终仍以 ZenMux API 为准：无效或无权访问的 slug 仍会返回 API 错误。

## 将 ZenMux 设为默认 Provider

```bash
hermes config set model.provider zenmux
hermes config set model.default google/gemini-2.5-flash-lite
hermes config set model.base_url https://zenmux.ai/api/v1
hermes config set model.api_mode chat_completions
```

验证：

```bash
hermes -z "Reply with exactly: OK" --safe-mode
```

## 模型目录行为

插件读取：

```text
https://zenmux.ai/api/v1/models
```

插件会：

- 保留输出文本的模型
- 从 Hermes 对话模型选择器中过滤纯图片/视频生成模型
- 保留完整的 `vendor/model` ID
- 不在代码中嵌入生成的模型目录快照
- 仅为目录暂时不可用的情况保留少量 fallback 模型

## 更新

GitHub 安装：

```bash
hermes plugins install ZenMux/hermes-plugin --force --enable
hermes gateway restart
```

PyPI 安装：

```bash
~/.hermes/hermes-agent/venv/bin/python -m pip install --upgrade zenmux-hermes-plugin
hermes gateway restart
```

## 卸载

GitHub 安装：

```bash
hermes auth logout zenmux
hermes plugins disable zenmux
rm -rf "${HERMES_HOME:-$HOME/.hermes}/plugins/zenmux"
```

PyPI 安装：

```bash
hermes auth logout zenmux
hermes plugins disable zenmux
~/.hermes/hermes-agent/venv/bin/python -m pip uninstall zenmux-hermes-plugin
```

## 故障排查

### `Unknown provider 'zenmux'`

```bash
hermes plugins list
hermes plugins enable zenmux
hermes gateway restart
```

### OAuth 授权超时

重新开始登录，并使用新生成的 URL 和端口。远程服务器需要转发该端口。过期登录流程
产生的 authorization code 不能复用。

### 已登录，但推理提示没有 endpoint

更新插件后重新登录。当前版本保存的凭据会包含：

```text
base_url=https://zenmux.ai/api/v1
```

早期开发版本未保存该字段。

### 模型因不在目录中而被拒绝

先确认完整 slug 是否正确。如 slug 确实有效但未出现在公开目录，请将 Hermes 更新到
支持 `model_listing_authoritative` 的版本，再更新本插件。

### 代理环境

使用标准 `HTTP_PROXY`/`HTTPS_PROXY`。如果本地代理会终止 TLS，应通过
`SSL_CERT_FILE`/`REQUESTS_CA_BUNDLE` 配置其 CA。不要全局关闭 TLS 校验。

## 开发

```bash
pytest -q tests
ruff check .
python -m build
twine check dist/*
```

开发时如需使用另一个已注册的 public OAuth client：

```bash
python3 configure.py zpc_YOUR_DEVELOPMENT_CLIENT_ID
```

## 安全设计

- 授权和 token endpoint 必须使用 HTTPS
- 回调服务器只监听 `127.0.0.1`
- 使用常量时间比较 OAuth `state`
- 使用 S256 PKCE
- 不使用 client secret
- 不记录 token、authorization code、state 或 PKCE verifier
- 通过 Hermes 凭据锁串行化 refresh token 轮换
- 校验 token endpoint host allowlist

## 许可证

MIT
