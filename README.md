# mcp-gtm-audit

[![PyPI](https://img.shields.io/pypi/v/mcp-gtm-audit.svg)](https://pypi.org/project/mcp-gtm-audit/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

MCP (Model Context Protocol) server for **Google Tag Manager** auditing. Lets Claude, Cursor, Zed and any MCP-compatible client inspect containers, generate full HTML audit reports, diff workspaces against published versions, and validate GA4 / Google Ads / Meta tracking implementations.

## Features

- **Inventory**: list accounts, containers, workspaces, tags, triggers, variables, versions
- **Automated audit**: detects tags without triggers, paused tags, custom HTML risks, GA4 misconfiguration (missing Measurement ID, missing event name), missing Consent Mode v2 settings, references to deleted variables, duplicates by signature, orphan triggers, unused variables, default/duplicate naming
- **Workspace diff**: compare a workspace against the live version (or two arbitrary versions) and get added / removed / modified entities per kind
- **Tracking validation**: maps GA4 events per Measurement ID, checks ecommerce parameters (`purchase`, `begin_checkout`, `add_to_cart`, `view_item`, `generate_lead`), Google Ads conversions and Conversion Linker presence, Meta Pixel detection, server-side tagging hints
- **HTML + JSON reports** written to `~/Reports/<slug>/gtm-audit-YYYYMMDD-HHMM.{html,json}`

## Installation

Until the package lands on PyPI, install straight from GitHub:

```bash
pipx install "git+https://github.com/acamolese/gtm-audit-mcp.git"
```

Or with `uv`:

```bash
uv tool install "git+https://github.com/acamolese/gtm-audit-mcp.git"
```

> **Setting this up with an AI coding agent?** Point it at
> [SETUP-FOR-AI-AGENTS.md](SETUP-FOR-AI-AGENTS.md): a step-by-step guide written
> for Claude Code, Claude Desktop, Cursor and similar tools, including the
> Google Cloud OAuth steps that need a human in the browser.

## Authorization

You need an OAuth client (Desktop application type) from Google Cloud Console with the **Tag Manager API** enabled.

### Option A — environment variables (stateless)

```bash
export GTM_CLIENT_ID="..."
export GTM_CLIENT_SECRET="..."
export GTM_REFRESH_TOKEN="..."
```

### Option B — interactive flow

1. Place `oauth_credentials.json` (downloaded from Google Cloud Console) in `~/.config/mcp-gtm-audit/`
2. Run:

   ```bash
   mcp-gtm-audit auth
   ```

   This prints the authorization URL, opens your browser, listens on `http://localhost:8080` for the callback, and saves the refresh token to `~/.config/mcp-gtm-audit/token.json`.

   Note: if the OAuth consent screen is in *Testing* mode, Google expires the refresh token after 7 days; re-run `mcp-gtm-audit auth` or publish the consent screen.

The required OAuth scope is `https://www.googleapis.com/auth/tagmanager.readonly`.

## MCP client configuration

### Claude Code (`~/.claude/.mcp.json`)

```json
{
  "mcpServers": {
    "gtm-audit": {
      "command": "mcp-gtm-audit"
    }
  }
}
```

### Claude Desktop (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS)

```json
{
  "mcpServers": {
    "gtm-audit": {
      "command": "mcp-gtm-audit"
    }
  }
}
```

If you installed via pipx and the binary is not on your client's PATH, use the absolute path (e.g. `~/.local/bin/mcp-gtm-audit`).

## Tools exposed to the MCP client

| Tool | Description |
|---|---|
| `list_accounts` | All GTM accounts the authenticated user can access |
| `list_containers(account_id)` | Containers within an account |
| `list_workspaces(account_id, container_id)` | Workspaces within a container |
| `list_versions(account_id, container_id)` | Published version headers |
| `list_tags / list_triggers / list_variables` | Inventory of a workspace |
| `gtm_audit(...)` | Full audit, writes HTML + JSON report and returns paths |
| `gtm_diff(account_id, container_id, base_ref, head_ref, workspace_id)` | Diff between any two snapshots (`live`, version ID, or `workspace`) |
| `gtm_tracking_validation(...)` | GA4/Ads/Meta event map and tracking findings |

## Example prompts

- *"Audit the GTM container `GTM-ABC123` and tell me the high-severity issues."*
- *"Diff the Default Workspace against the live version of container 12345."*
- *"List all GA4 events tracked across my GTM account and flag any purchase events missing `transaction_id`."*

## Privacy

This server is read-only: it requests `tagmanager.readonly` and never writes to your container. Reports are stored locally under `~/Reports/`. No telemetry is sent anywhere.

## License

MIT — see [LICENSE](LICENSE).
