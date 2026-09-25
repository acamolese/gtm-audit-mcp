# Setup guide for AI agents (Claude Code, Claude Desktop, Cursor, Zed)

This file is written for an AI coding agent that has been asked to install and
configure `mcp-gtm-audit` on a user's machine. Follow the steps in order. Steps
marked **[human]** need the user to act in a browser; ask them to do it and wait.

The server is read-only (`tagmanager.readonly`) and talks to the Google Tag
Manager API v2. It exposes MCP tools over stdio.

## 0. Prerequisites to check

```bash
python3 --version        # needs >= 3.10
pipx --version || uv --version
```

If neither `pipx` nor `uv` is present, install one:

```bash
brew install pipx && pipx ensurepath      # macOS
# or
python3 -m pip install --user pipx && python3 -m pipx ensurepath
```

## 1. Install the package

The package is not yet published on PyPI. Install from GitHub:

```bash
pipx install "git+https://github.com/acamolese/gtm-audit-mcp.git"
# or
uv tool install "git+https://github.com/acamolese/gtm-audit-mcp.git"
```

For development from a local clone:

```bash
git clone https://github.com/acamolese/gtm-audit-mcp.git ~/gtm-audit-mcp
pipx install -e ~/gtm-audit-mcp
```

Verify the binary and record its absolute path (you will need it for the client config):

```bash
which mcp-gtm-audit      # typically ~/.local/bin/mcp-gtm-audit
```

## 2. Google Cloud OAuth client **[human]**

The user needs an OAuth client of type **Desktop app** in a Google Cloud
project where the **Tag Manager API** is enabled. Ask them to:

1. Open https://console.cloud.google.com/apis/library/tagmanager.googleapis.com and click **Enable**.
2. Open https://console.cloud.google.com/apis/credentials, click **Create credentials → OAuth client ID**, application type **Desktop app**.
3. If asked, configure the OAuth consent screen (External, testing mode is fine) and add their own Google account as a **test user**.
4. Download the client JSON.

Then place the file:

```bash
mkdir -p ~/.config/mcp-gtm-audit
mv ~/Downloads/client_secret_*.json ~/.config/mcp-gtm-audit/oauth_credentials.json
chmod 600 ~/.config/mcp-gtm-audit/oauth_credentials.json
```

Alternative without files: export `GTM_CLIENT_ID`, `GTM_CLIENT_SECRET` and
`GTM_REFRESH_TOKEN` in the environment the MCP client launches the server with.
Environment variables take precedence over the files.

## 3. Authorize **[human]**

Run the interactive flow. It prints the authorization URL, tries to open the
browser, and listens on `http://localhost:8080` for the callback.

```bash
mcp-gtm-audit auth
```

The user must sign in with a Google account that has access to the GTM
containers and click **Allow**. On success the refresh token is saved to
`~/.config/mcp-gtm-audit/token.json`.

If port 8080 is already in use, free it first (`lsof -i :8080`). The redirect
URI is fixed to `http://localhost:8080`, and Desktop-app clients accept any
localhost port, so nothing needs to be configured in Google Cloud for this.

## 4. Register the server in the MCP client

Use the absolute path from step 1. Do not rely on PATH: GUI apps such as
Claude Desktop do not read the shell profile.

### Claude Code

Either run:

```bash
claude mcp add --scope user gtm-audit -- ~/.local/bin/mcp-gtm-audit
```

or add to `~/.claude/.mcp.json`:

```json
{
  "mcpServers": {
    "gtm-audit": {
      "command": "/Users/<user>/.local/bin/mcp-gtm-audit"
    }
  }
}
```

### Claude Desktop (macOS)

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` and add
the same `gtm-audit` entry under `mcpServers`. Restart Claude Desktop.

### Cursor / Zed / other clients

Any client that supports stdio MCP servers works: command
`/absolute/path/to/mcp-gtm-audit`, no arguments, no extra environment unless
you chose the env-var credential option.

## 5. Verify

From the MCP client, call `list_accounts`. It should return the GTM accounts
visible to the authorized Google account. From the shell you can also check
that the server starts and stays up:

```bash
timeout 3 mcp-gtm-audit; echo "exit=$?"    # exit=124 means it was running fine and got killed by timeout
```

## Tools available after setup

| Tool | Purpose |
|---|---|
| `list_accounts` | GTM accounts visible to the user |
| `list_containers(account_id)` | Containers in an account |
| `list_workspaces(account_id, container_id)` | Workspaces in a container |
| `list_versions(account_id, container_id)` | Published version headers |
| `list_tags / list_triggers / list_variables(account_id, container_id, workspace_id)` | Inventory |
| `gtm_audit(...)` | Full audit; writes HTML + JSON to `~/Reports/<slug>/` and returns the paths |
| `gtm_diff(account_id, container_id, base_ref, head_ref, workspace_id)` | Diff between `live`, a version ID, or `workspace` |
| `gtm_tracking_validation(...)` | GA4 / Google Ads / Meta event map and findings |

## Troubleshooting

- **`invalid_grant` or 401 after a few days**: if the OAuth consent screen is
  in *Testing* mode, Google expires refresh tokens after 7 days. Run
  `mcp-gtm-audit auth` again. To avoid this, publish the consent screen
  (status *In production*); no verification is required for the
  `tagmanager.readonly` scope on an internal or low-usage app.
- **`No OAuth client found`**: `~/.config/mcp-gtm-audit/oauth_credentials.json`
  is missing or not valid JSON, and the `GTM_*` env vars are not set.
- **Server not listed in the client**: the `command` path is not absolute or
  the client was not restarted after editing the config.
- **`Address already in use` during auth**: another process holds port 8080.
- **403 on a container**: the authorized Google account lacks read access to
  that container in GTM, not a server problem.

## What not to do

- Do not commit `oauth_credentials.json` or `token.json` anywhere. Both are
  gitignored in this repository on purpose.
- Do not paste the client secret or refresh token into chat, logs or reports.
- Do not request write scopes: the server only needs `tagmanager.readonly`.
