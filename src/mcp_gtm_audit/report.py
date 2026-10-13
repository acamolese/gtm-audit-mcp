"""Self-contained HTML report of an audit run."""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from typing import Any

from . import i18n

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}
SEVERITY_COLORS = {"high": "#c0392b", "medium": "#e67e22", "low": "#7f8c8d"}


def render_audit_html(
    audit: dict[str, Any],
    container_label: str,
    tracking: dict[str, Any] | None = None,
    language: str = "en",
) -> str:
    lang = i18n.normalize_language(language)

    def tr(key: str, **params) -> str:
        return escape(i18n.t(lang, key, **params))

    issues = sorted(audit["issues"], key=lambda i: (SEVERITY_ORDER.get(i["severity"], 9), i["code"]))
    stats = audit["stats"]
    snap = audit["snapshot"]
    generated = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")

    rows = "\n".join(_issue_row(i) for i in issues) or f"<tr><td colspan='4'>{tr('report.no_issues')}</td></tr>"
    type_rows = (
        "\n".join(
            f"<tr><td>{escape(t)}</td><td>{n}</td></tr>"
            for t, n in sorted(stats.get("tags_by_type", {}).items(), key=lambda x: -x[1])
        )
        or f"<tr><td colspan='2'>{tr('report.no_tags')}</td></tr>"
    )

    tracking_html = _render_tracking(tracking, lang) if tracking else ""
    workspace = f"· workspace {escape(str(snap.get('workspaceId')))}" if snap.get("workspaceId") else ""
    version = f"· version {escape(str(snap.get('versionId')))}" if snap.get("versionId") else ""

    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<title>GTM Audit · {escape(container_label)}</title>
<style>
  :root {{ --bg:#f4f5f7; --card:#fff; --border:#e2e6ea; --text:#1f2933; }}
  body {{ margin:0; padding:32px; background:var(--bg); color:var(--text);
         font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
  h1 {{ margin:0 0 4px; font-size:24px; }}
  h2 {{ margin:32px 0 12px; font-size:18px; }}
  .meta {{ color:#5f6b7a; font-size:14px; margin-bottom:24px; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:12px; }}
  .stat {{ background:var(--card); border:1px solid var(--border); border-radius:8px; padding:16px; }}
  .stat .num {{ font-size:28px; font-weight:600; }}
  .stat .label {{ color:#5f6b7a; font-size:13px; margin-top:4px; }}
  table {{ width:100%; border-collapse:collapse; background:var(--card);
          border:1px solid var(--border); border-radius:8px; overflow:hidden; }}
  th, td {{ padding:10px 12px; text-align:left; border-bottom:1px solid var(--border); font-size:14px; vertical-align:top; }}
  th {{ background:#f7f9fb; font-weight:600; font-size:13px; color:#52606d; }}
  tr:last-child td {{ border-bottom:none; }}
  .badge {{ display:inline-block; padding:2px 8px; border-radius:12px; color:#fff; font-size:11px; text-transform:uppercase; letter-spacing:.4px; }}
  .small {{ font-size:12px; color:#5f6b7a; }}
  code {{ background:#eef1f4; padding:1px 5px; border-radius:4px; font-size:12px; }}
</style>
</head>
<body>
<h1>{tr("report.title")}</h1>
<div class="meta">{escape(container_label)} · {tr("report.generated")} {generated}</div>

<div class="grid">
  <div class="stat"><div class="num">{stats.get("tags", 0)}</div><div class="label">{tr("report.tags")}</div></div>
  <div class="stat"><div class="num">{stats.get("triggers", 0)}</div><div class="label">{tr("report.triggers")}</div></div>
  <div class="stat"><div class="num">{stats.get("variables", 0)}</div><div class="label">{tr("report.variables")}</div></div>
  <div class="stat"><div class="num" style="color:{SEVERITY_COLORS["high"]}">{stats.get("issues_high", 0)}</div><div class="label">{tr("report.high")}</div></div>
  <div class="stat"><div class="num" style="color:{SEVERITY_COLORS["medium"]}">{stats.get("issues_medium", 0)}</div><div class="label">{tr("report.medium")}</div></div>
  <div class="stat"><div class="num" style="color:{SEVERITY_COLORS["low"]}">{stats.get("issues_low", 0)}</div><div class="label">{tr("report.low")}</div></div>
</div>

<h2>{tr("report.by_type")}</h2>
<table>
  <thead><tr><th>{tr("report.type")}</th><th>{tr("report.count")}</th></tr></thead>
  <tbody>{type_rows}</tbody>
</table>

<h2>{tr("report.issues", n=len(issues))}</h2>
<table>
  <thead><tr><th>{tr("report.severity")}</th><th>{tr("report.code")}</th><th>{tr("report.entity")}</th><th>{tr("report.detail")}</th></tr></thead>
  <tbody>{rows}</tbody>
</table>

{tracking_html}

<p class="small" style="margin-top:32px;">{tr("report.snapshot")}: {escape(str(snap.get("source") or ""))}
  · account {escape(str(snap.get("accountId") or ""))} · container {escape(str(snap.get("containerId") or ""))}
  {workspace} {version}
</p>
</body>
</html>"""


def _issue_row(i: dict) -> str:
    color = SEVERITY_COLORS.get(i["severity"], "#666")
    entity = escape(f"{i.get('entity_type', '')}: {i.get('entity_name', '')}".strip(": "))
    return (
        f"<tr>"
        f"<td><span class='badge' style='background:{color}'>{i['severity']}</span></td>"
        f"<td><code>{escape(i['code'])}</code><div class='small'>{escape(i['title'])}</div></td>"
        f"<td>{entity}</td>"
        f"<td>{escape(i['detail'])}</td>"
        f"</tr>"
    )


def _render_tracking(tracking: dict[str, Any], lang: str) -> str:
    def tr(key: str, **params) -> str:
        return escape(i18n.t(lang, key, **params))

    findings = tracking.get("findings") or []
    rows = (
        "\n".join(
            f"<tr><td><span class='badge' style='background:{SEVERITY_COLORS.get(f['severity'], '#666')}'>"
            f"{f['severity']}</span></td><td>{escape(f['tag'])}</td><td>{escape(f['issue'])}</td></tr>"
            for f in findings
        )
        or f"<tr><td colspan='3'>{tr('report.no_findings')}</td></tr>"
    )

    ga4_rows = (
        "\n".join(
            f"<tr><td>{escape(c.get('name', ''))}</td>"
            f"<td><code>{escape(c.get('measurementId') or '—')}</code></td>"
            f"<td>{escape(c.get('server_container_url') or '—')}</td></tr>"
            for c in tracking.get("ga4_configs", [])
        )
        or f"<tr><td colspan='3'>{tr('report.no_ga4')}</td></tr>"
    )

    ads_rows = (
        "\n".join(
            f"<tr><td>{escape(c.get('name', ''))}</td>"
            f"<td><code>{escape(c.get('conversionId') or '—')}</code></td>"
            f"<td><code>{escape(c.get('conversionLabel') or '—')}</code></td></tr>"
            for c in tracking.get("ads_conversions", [])
        )
        or f"<tr><td colspan='3'>{tr('report.no_ads')}</td></tr>"
    )

    return f"""
<h2>{tr("report.tracking")}</h2>
<table>
  <thead><tr><th>{tr("report.severity")}</th><th>{tr("report.tag")}</th><th>{tr("report.issue")}</th></tr></thead>
  <tbody>{rows}</tbody>
</table>

<h2>{tr("report.ga4_configs")}</h2>
<table>
  <thead><tr><th>{tr("report.tag")}</th><th>{tr("report.measurement_id")}</th><th>{tr("report.server_container")}</th></tr></thead>
  <tbody>{ga4_rows}</tbody>
</table>

<h2>{tr("report.ads")}</h2>
<table>
  <thead><tr><th>{tr("report.tag")}</th><th>{tr("report.conversion_id")}</th><th>{tr("report.conversion_label")}</th></tr></thead>
  <tbody>{ads_rows}</tbody>
</table>
"""
