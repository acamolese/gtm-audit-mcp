"""Generazione report HTML dell'audit GTM."""

from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}
SEVERITY_COLORS = {
    "high": "#c0392b",
    "medium": "#e67e22",
    "low": "#7f8c8d",
}


def render_audit_html(
    audit: dict[str, Any],
    container_label: str,
    tracking: dict[str, Any] | None = None,
) -> str:
    issues = sorted(audit["issues"], key=lambda i: (SEVERITY_ORDER.get(i["severity"], 9), i["code"]))
    stats = audit["stats"]
    snap = audit["snapshot"]
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")

    rows = "\n".join(_issue_row(i) for i in issues) or _empty_row()
    type_rows = "\n".join(
        f"<tr><td>{escape(t)}</td><td>{n}</td></tr>"
        for t, n in sorted(stats.get("tags_by_type", {}).items(), key=lambda x: -x[1])
    ) or "<tr><td colspan='2'>Nessun tag</td></tr>"

    tracking_html = _render_tracking(tracking) if tracking else ""

    return f"""<!doctype html>
<html lang="it">
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
<h1>Audit Google Tag Manager</h1>
<div class="meta">{escape(container_label)} · generato {generated}</div>

<div class="grid">
  <div class="stat"><div class="num">{stats.get('tags', 0)}</div><div class="label">Tag</div></div>
  <div class="stat"><div class="num">{stats.get('triggers', 0)}</div><div class="label">Trigger</div></div>
  <div class="stat"><div class="num">{stats.get('variables', 0)}</div><div class="label">Variabili</div></div>
  <div class="stat"><div class="num" style="color:{SEVERITY_COLORS['high']}">{stats.get('issues_high', 0)}</div><div class="label">Criticità alta</div></div>
  <div class="stat"><div class="num" style="color:{SEVERITY_COLORS['medium']}">{stats.get('issues_medium', 0)}</div><div class="label">Media</div></div>
  <div class="stat"><div class="num" style="color:{SEVERITY_COLORS['low']}">{stats.get('issues_low', 0)}</div><div class="label">Bassa</div></div>
</div>

<h2>Distribuzione tag per tipo</h2>
<table>
  <thead><tr><th>Tipo</th><th>Conteggio</th></tr></thead>
  <tbody>{type_rows}</tbody>
</table>

<h2>Criticità rilevate ({len(issues)})</h2>
<table>
  <thead><tr><th>Severità</th><th>Codice</th><th>Entità</th><th>Dettaglio</th></tr></thead>
  <tbody>{rows}</tbody>
</table>

{tracking_html}

<p class="small" style="margin-top:32px;">Snapshot: {escape(snap.get('source') or '')}
  · account {escape(snap.get('accountId') or '')} · container {escape(snap.get('containerId') or '')}
  {f"· workspace {escape(snap.get('workspaceId') or '')}" if snap.get('workspaceId') else ''}
  {f"· version {escape(str(snap.get('versionId') or ''))}" if snap.get('versionId') else ''}
</p>
</body>
</html>"""


def _issue_row(i: dict) -> str:
    color = SEVERITY_COLORS.get(i["severity"], "#666")
    entity = escape(f"{i.get('entity_type','')}: {i.get('entity_name','')}".strip(": "))
    return (
        f"<tr>"
        f"<td><span class='badge' style='background:{color}'>{i['severity']}</span></td>"
        f"<td><code>{escape(i['code'])}</code><div class='small'>{escape(i['title'])}</div></td>"
        f"<td>{entity}</td>"
        f"<td>{escape(i['detail'])}</td>"
        f"</tr>"
    )


def _empty_row() -> str:
    return "<tr><td colspan='4'>Nessuna criticità rilevata 🎉</td></tr>"


def _render_tracking(tracking: dict[str, Any]) -> str:
    findings = tracking.get("findings") or []
    rows = "\n".join(
        f"<tr><td><span class='badge' style='background:{SEVERITY_COLORS.get(f['severity'], '#666')}'>"
        f"{f['severity']}</span></td><td>{escape(f['tag'])}</td><td>{escape(f['issue'])}</td></tr>"
        for f in findings
    ) or "<tr><td colspan='3'>Nessun finding di tracciamento</td></tr>"

    ga4_rows = "\n".join(
        f"<tr><td>{escape(c.get('name',''))}</td>"
        f"<td><code>{escape(c.get('measurementId') or '—')}</code></td>"
        f"<td>{escape(c.get('server_container_url') or '—')}</td></tr>"
        for c in tracking.get("ga4_configs", [])
    ) or "<tr><td colspan='3'>Nessuna GA4 Configuration</td></tr>"

    ads_rows = "\n".join(
        f"<tr><td>{escape(c.get('name',''))}</td>"
        f"<td><code>{escape(c.get('conversionId') or '—')}</code></td>"
        f"<td><code>{escape(c.get('conversionLabel') or '—')}</code></td></tr>"
        for c in tracking.get("ads_conversions", [])
    ) or "<tr><td colspan='3'>Nessuna conversione Google Ads</td></tr>"

    return f"""
<h2>Validazione tracciamento</h2>
<table>
  <thead><tr><th>Severità</th><th>Tag</th><th>Issue</th></tr></thead>
  <tbody>{rows}</tbody>
</table>

<h2>GA4 Configurations</h2>
<table>
  <thead><tr><th>Tag</th><th>Measurement ID</th><th>Server container</th></tr></thead>
  <tbody>{ga4_rows}</tbody>
</table>

<h2>Google Ads Conversions</h2>
<table>
  <thead><tr><th>Tag</th><th>Conversion ID</th><th>Conversion Label</th></tr></thead>
  <tbody>{ads_rows}</tbody>
</table>
"""
