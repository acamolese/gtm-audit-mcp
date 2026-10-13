# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [0.2.0] - 2026-10-13

### Added
- **Opt-in write mode.** With `GTM_ALLOW_WRITE=1` the server registers
  `create_workspace`, `delete_workspace`, `create_tag`, `update_tag`, `create_trigger`,
  `update_trigger`, `create_variable`, `update_variable` and `delete_entity`.
  Writes only touch workspaces, refuse the Default Workspace unless told
  otherwise, and every response ends with the same instruction: review in
  Preview, then version and publish from the GTM UI. There is no publish tool
  and no version tool, and the publish scopes are never requested.
- `gtm_export`: writes a container export in GTM's own import format, from a
  workspace or the live version, for Admin > Import container.
- `get_entity`: one tag, trigger, variable or folder in full, to copy the
  resource shape before a create or update.
- `gtm_doctor` tool and `mcp-gtm-audit doctor` command: credentials, granted
  scopes, write mode and API reachability in one call.
- `language` argument (`en`, `it`) on `gtm_audit` and `gtm_tracking_validation`;
  the HTML report and every issue text follow it. English is the default.
- Client-side rate limiting (15 requests per minute sliding window) and
  retries on 429 and 5xx, matching the Tag Manager API quota. Writes are
  spaced 4 seconds apart with a longer back-off, since Google meters them
  separately.
- Test suite, CI on three platforms, release workflow with PyPI trusted
  publishing, stdio smoke test.

### Changed
- Tool docstrings, error messages and the CLI are in English.
- `gtm_audit` returns the issues and tracking findings inline, not only the
  report paths. The reports directory can be set with `GTM_REPORTS_DIR`.
- The OAuth flow picks a free localhost port when 8080 is taken, records the
  scopes Google actually granted, and asks for the edit scope only in write mode.
- `mcp-gtm-audit auth` output no longer prints the refresh token.
- Supports both `mcp` 1.x and 2.x through a small compatibility shim.

### Fixed
- `gtm_diff` reported every entity as modified when comparing a version to a
  workspace, because `tagManagerUrl` differs between the two. Volatile fields
  are now ignored and each modified entity lists the fields that changed, with
  before and after values.
- GA4 event parameters are read from the Google tag's `eventSettingsTable`
  shape, so the ecommerce parameter check no longer reports every parameter as
  missing.
- Built-in Consent Initialization and Initialization triggers are no longer
  reported as orphan triggers.

## [0.1.0] - 2026-05-08

Initial release: inventory, audit, diff, tracking validation, HTML report.
