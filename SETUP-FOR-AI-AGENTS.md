# Setup guide for AI agents (Claude Code, Claude Desktop, Cursor, Codex)

This file is written for an AI coding agent asked to install and configure
`mcp-gtm-audit` on a user's machine. Follow the steps in order. Steps marked
**[human]** need the user to act in a browser: ask them to do it and wait.

The server talks to the Google Tag Manager API v2 over stdio. It is read-only
by default (`tagmanager.readonly`). An optional write mode adds
`tagmanager.edit.containers` and lets it change workspaces; it never creates a
version and never publishes.

## 0. Prerequisites

```bash
python3 --version        # needs >= 3.10
pipx --version || uv --version
```

If neither `pipx` nor `uv` is present:

```bash
brew install pipx && pipx ensurepath      # macOS
# or
python3 -m pip install --user pipx && python3 -m pipx ensurepath
```

## 1. Install

```bash
pipx install mcp-gtm-audit
# or
uv tool install mcp-gtm-audit
```

From a local clone, for development: `pipx install -e ~/gtm-audit-mcp`.

Record the absolute path of the binary, the client config needs it:

```bash
which mcp-gtm-audit      # typically ~/.local/bin/mcp-gtm-audit
mcp-gtm-audit version
```

## 2. Google Cloud OAuth client **[human]**

The user needs an OAuth client of type **Desktop app** in a Google Cloud
project with the **Tag Manager API** enabled. Ask them to:

1. Open https://console.cloud.google.com/apis/library/tagmanager.googleapis.com and click **Enable**.
2. Open https://console.cloud.google.com/apis/credentials, **Create credentials > OAuth client ID**, type **Desktop app**.
3. If asked, configure the consent screen (External, Testing is fine) and add their Google account as a **test user**.
4. Download the client JSON.

Then place it:

```bash
mkdir -p ~/.config/mcp-gtm-audit
mv ~/Downloads/client_secret_*.json ~/.config/mcp-gtm-audit/oauth_credentials.json
chmod 600 ~/.config/mcp-gtm-audit/oauth_credentials.json
```

Alternative without files: `GTM_CLIENT_ID`, `GTM_CLIENT_SECRET` and
`GTM_REFRESH_TOKEN` in the environment the MCP client launches the server
with. Environment variables win over the files.

## 3. Authorize **[human]**

```bash
mcp-gtm-audit auth                      # read-only
GTM_ALLOW_WRITE=1 mcp-gtm-audit auth    # read + edit containers, only if the user wants write mode
```

It prints the URL, opens the browser and listens on a localhost port (8080,
or a free one if that is taken) for the callback. The user signs in with an
account that has access to the containers and clicks **Allow**. The refresh
token is saved to `~/.config/mcp-gtm-audit/token.json` with mode 600.

Decide the mode with the user before this step: the token records the scopes
Google granted, and a read-only token cannot write. Switching later is one
more `auth` run.

## 4. Register the server in the MCP client

Use the absolute path from step 1. GUI apps do not read the shell profile.

Claude Code:

```bash
claude mcp add --scope user gtm-audit -- ~/.local/bin/mcp-gtm-audit
# write mode:
claude mcp add --scope user -e GTM_ALLOW_WRITE=1 gtm-audit -- ~/.local/bin/mcp-gtm-audit
```

Claude Desktop (`~/Library/Application Support/Claude/claude_desktop_config.json`
on macOS), Cursor, Codex and any stdio client:

```json
{
  "mcpServers": {
    "gtm-audit": {
      "command": "/Users/<user>/.local/bin/mcp-gtm-audit",
      "env": { "GTM_ALLOW_WRITE": "1" }
    }
  }
}
```

Leave `env` out for read-only. Restart the client after editing the config.

## 5. Verify

```bash
mcp-gtm-audit doctor
```

prints the package version, the mode, the scopes the token carries and how
many accounts are visible; exit code 0 means the API answered. From the MCP
client, call `gtm_doctor`, then `list_accounts`.

## Tools after setup

Always available: `gtm_doctor`, `list_accounts`, `list_containers`,
`list_workspaces`, `list_versions`, `list_tags`, `list_triggers`,
`list_variables`, `get_entity`, `gtm_audit`, `gtm_tracking_validation`,
`gtm_diff`, `gtm_export`.

With `GTM_ALLOW_WRITE=1`: `create_workspace`, `delete_workspace`, `create_tag`, `update_tag`,
`create_trigger`, `update_trigger`, `create_variable`, `update_variable`,
`delete_entity`. They refuse the Default Workspace unless
`allow_default_workspace=true`, and every answer ends with the next step:
review in Preview, then version and publish from the GTM UI.

`container_id` is the numeric id from `list_containers`, not the `GTM-XXXX`
public id. Reports and exports land in `~/Reports/<container>/` unless
`GTM_REPORTS_DIR` or an explicit `output_dir` / `output_path` says otherwise.

## Troubleshooting

- **`invalid_grant` or 401 after a few days**: consent screen in *Testing*,
  Google expires refresh tokens after 7 days. Run `auth` again, or publish the
  consent screen (no verification needed for these scopes on a low-usage app).
- **"GTM_ALLOW_WRITE is set but the saved token only has the read-only scope"**:
  run `GTM_ALLOW_WRITE=1 mcp-gtm-audit auth` once.
- **`No OAuth client credentials found`**: the JSON is missing from
  `~/.config/mcp-gtm-audit/` and the `GTM_*` variables are not set.
- **Server not listed in the client**: the `command` path is not absolute, or
  the client was not restarted.
- **403 on a container**: the authorized account lacks access to that
  container in GTM, or write mode was used with a read-only token.
- **429 / slow calls**: the Tag Manager API allows 15 requests per minute per
  user. The client throttles and retries; a full workspace snapshot is 5 to 6
  calls, an audit plus a diff fits in the window.
- **429 on writes only, for minutes**: writes are metered separately and much
  more tightly than reads. The client spaces them 4 seconds apart and backs
  off up to 90 seconds; if the quota does not come back, stop and retry later,
  one change at a time. The exact numbers are on the Tag Manager API quota page
  of the Google Cloud project that owns the OAuth client.

## What not to do

- Do not commit `oauth_credentials.json` or `token.json`. Both are gitignored.
- Do not paste the client secret or refresh token into chat, logs or reports.
- Do not ask for publish scopes: the server has no publish tool by design.
- Do not write into the Default Workspace unless the user explicitly says so.
