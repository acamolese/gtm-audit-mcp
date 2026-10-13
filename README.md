# mcp-gtm-audit

[![PyPI](https://img.shields.io/pypi/v/mcp-gtm-audit.svg)](https://pypi.org/project/mcp-gtm-audit/)
[![CI](https://github.com/acamolese/gtm-audit-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/acamolese/gtm-audit-mcp/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

MCP (Model Context Protocol) server for **Google Tag Manager**. It lets Claude
Code, Claude Desktop, Cursor, Codex and any MCP client audit a container,
validate GA4 / Google Ads / Meta tracking, diff a workspace against the live
version, export an importable container JSON and, when you opt in, apply a
reviewed set of changes inside a workspace.

It never publishes. Versions and publishing stay in the GTM UI, after a human
has looked at the workspace in Preview.

## What it does

- **Inventory**: accounts, containers, workspaces, versions, tags, triggers,
  variables, and any single entity in full.
- **Audit** (`gtm_audit`): tags without triggers, paused tags, Custom HTML
  risks, Google tag without Measurement ID, GA4 events without name or
  Measurement ID, missing Consent Mode checks, references to deleted
  variables, duplicated tags, orphan triggers, unused variables, duplicated
  and default names. HTML plus JSON report, in English or Italian.
- **Tracking validation** (`gtm_tracking_validation`): GA4 events per
  Measurement ID with their parameters, missing ecommerce parameters
  (`purchase`, `begin_checkout`, `add_to_cart`, `view_item`, `generate_lead`),
  Google Ads conversions and Conversion Linker, Meta pixels, server-side
  tagging detection (also through "Google tag: Configuration settings"
  variables).
- **Diff** (`gtm_diff`): live version vs workspace, or any two versions, with
  the fields that changed and their before/after values.
- **Export** (`gtm_export`): a file in GTM's own export format, importable
  from Admin > Import container.
- **Write mode** (opt-in): create a workspace, create / update / delete tags,
  triggers and variables inside it. See below.
- **Doctor** (`gtm_doctor`, `mcp-gtm-audit doctor`): credentials, granted
  scopes, mode and API reachability in one call.

## Install

```bash
pipx install mcp-gtm-audit
# or
uv tool install mcp-gtm-audit
```

Setting it up with an AI agent? Point it at
[SETUP-FOR-AI-AGENTS.md](SETUP-FOR-AI-AGENTS.md): install, Google Cloud OAuth
client, authorization, client configuration and troubleshooting, with the
steps that need a human in the browser marked.

## Authorize

You need an OAuth client (Desktop application) from a Google Cloud project
with the **Tag Manager API** enabled.

Option A, environment variables (stateless, good for CI and containers):

```bash
export GTM_CLIENT_ID="..."
export GTM_CLIENT_SECRET="..."
export GTM_REFRESH_TOKEN="..."
```

Option B, interactive flow:

1. Put the downloaded client JSON at `~/.config/mcp-gtm-audit/oauth_credentials.json`.
2. Run `mcp-gtm-audit auth`. It opens the browser, listens on a localhost
   port for the callback and saves the refresh token to
   `~/.config/mcp-gtm-audit/token.json`.

The read-only mode asks for `tagmanager.readonly` only. If the OAuth consent
screen is in *Testing*, Google expires refresh tokens after 7 days: run
`mcp-gtm-audit auth` again or publish the consent screen.

## Configure the client

Claude Code:

```bash
claude mcp add --scope user gtm-audit -- mcp-gtm-audit
```

Claude Desktop, Cursor, Codex and others, in their MCP configuration:

```json
{
  "mcpServers": {
    "gtm-audit": {
      "command": "/absolute/path/to/mcp-gtm-audit"
    }
  }
}
```

Use the absolute path (`which mcp-gtm-audit`): GUI apps do not read your shell
profile.

## Tools

| Tool | What it returns |
|---|---|
| `gtm_doctor` | credentials, scopes, write mode, number of accounts visible |
| `list_accounts` | GTM accounts |
| `list_containers(account_id)` | containers with the numeric `containerId` the other tools need |
| `list_workspaces(account_id, container_id)` | workspaces |
| `list_versions(account_id, container_id)` | published version headers |
| `list_tags` / `list_triggers` / `list_variables(account_id, container_id, workspace_id)` | inventory of a workspace |
| `get_entity(account_id, container_id, kind, entity_id, workspace_id)` | one tag / trigger / variable / folder in full |
| `gtm_audit(account_id, container_id, workspace_id, use_live_version, output_dir, client_slug, language)` | issues, stats, tracking findings and the HTML + JSON report paths |
| `gtm_tracking_validation(account_id, container_id, workspace_id, use_live_version, language)` | GA4 / Ads / Meta event map and findings |
| `gtm_diff(account_id, container_id, base_ref, head_ref, workspace_id)` | added / removed / modified entities between `live`, a version id or `workspace` |
| `gtm_export(account_id, container_id, workspace_id, use_live_version, output_path)` | path of the importable container JSON |

Write tools, registered only with `GTM_ALLOW_WRITE=1`:

| Tool | Notes |
|---|---|
| `create_workspace(account_id, container_id, name, description)` | where every change set should live |
| `delete_workspace(account_id, container_id, workspace_id)` | clean-up after the change set was published or abandoned |
| `create_tag` / `create_trigger` / `create_variable(account_id, container_id, workspace_id, *_json)` | the body is a JSON resource; copy the shape from `get_entity` |
| `update_tag` / `update_trigger` / `update_variable(..., entity_id, *_json)` | read-merge-write with the fingerprint; pass only the fields to change |
| `delete_entity(account_id, container_id, workspace_id, kind, entity_id)` | reversible until the workspace is published |

Reports and exports go to `~/Reports/<container>/` by default; set
`GTM_REPORTS_DIR` to change the base folder.

## Write mode and its limits

```bash
GTM_ALLOW_WRITE=1 mcp-gtm-audit auth    # once, grants tagmanager.edit.containers
```

and start the server with `GTM_ALLOW_WRITE=1` in its environment. Then:

- Writes go to a workspace. By default the tools refuse the **Default
  Workspace**, because other people's unpublished work lives there; create a
  dedicated one with `create_workspace`.
- There is no `publish` and no `create_version` tool, and the publish scopes
  are never requested. Every write answers with the same next step: review in
  GTM Preview, then version and publish from the UI.
- Prefer `gtm_diff` (live vs workspace) before handing a workspace over.
- Writes are metered by Google much more tightly than reads: the client spaces
  them out and backs off, but a long burst still ends in 429 for minutes. Plan
  change sets of a handful of entities, not a full container rebuild.
- Without write mode the same changes can travel as a file: `gtm_export`,
  edit the JSON, import it from Admin > Import container into a workspace.

## Example prompts

- "Audit container GTM-ABC123 and list the high-severity issues."
- "Diff the workspace 'Consent fix' against the live version."
- "Map every GA4 event per Measurement ID and flag purchase events without `transaction_id`."
- "Create a workspace 'Server-side GA4' and move the Google tag to a configuration variable with `server_container_url`."

## Development

```bash
uv venv && uv pip install -e ".[dev]"
ruff check src tests && ruff format --check src tests
pytest -q
python scripts/smoke_stdio.py --command .venv/bin/mcp-gtm-audit
```

Releases go out from a tag (`vX.Y.Z`): the workflow runs the suite, builds
the wheel and sdist, publishes to PyPI with trusted publishing and creates the
GitHub Release from the matching CHANGELOG section.

## Privacy

Read-only by default (`tagmanager.readonly`). Write mode adds
`tagmanager.edit.containers` and nothing else. Reports and exports are written
locally. No telemetry.

## License

MIT, see [LICENSE](LICENSE).
