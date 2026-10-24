#!/usr/bin/env python3
"""Collect GitHub release download counts over time and render them as an SVG chart.

Why this script exists
----------------------
GitHub's REST API exposes only a *current* cumulative `download_count` per
release asset. There is no historical time series, so a trend chart can only be
built by sampling the API on a schedule and keeping the samples.

There is a second, project-specific reason. `.github/workflows/weekly-release.yml`
prunes old releases and keeps only the 3 most recent ones. As soon as a release
is deleted its assets (and their counts) disappear from the API -- a naive
"sum all releases" total would therefore *drop*. This script records counts per
release tag and freezes the last known value of any release that has vanished,
so the running total never decreases.

Outputs
-------
  assets/downloads-history.json    snapshot history (the source of truth)
  assets/downloads-chart.svg       light-theme chart
  assets/downloads-chart-dark.svg  dark-theme chart

Standard library only -- no pip install needed.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

API_ROOT = "https://api.github.com"
HISTORY_SCHEMA = 1
USER_AGENT = "codex-desktop-portable-download-stats"

# --------------------------------------------------------------------------
# palettes -- one per GitHub colour scheme
# --------------------------------------------------------------------------
LIGHT = {
    "grid": "#eaeef2",
    "axis": "#d0d7de",
    "muted": "#656d76",
    "text": "#1f2328",
    "line": "#0969da",
    "line_soft": "#54aeff",
    "area_opacity": "0.20",
    "dot_stroke": "#ffffff",
}

DARK = {
    "grid": "#21262d",
    "axis": "#30363d",
    "muted": "#8b949e",
    "text": "#e6edf3",
    "line": "#2f81f7",
    "line_soft": "#58a6ff",
    "area_opacity": "0.24",
    "dot_stroke": "#0d1117",
}


# --------------------------------------------------------------------------
# GitHub API
# --------------------------------------------------------------------------
def api_json(url: str, token: str | None):
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": USER_AGENT,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_releases(repo: str, token: str | None) -> list[dict]:
    """Return every published (non-draft) release, following pagination."""
    releases: list[dict] = []
    page = 1
    while True:
        url = f"{API_ROOT}/repos/{repo}/releases?per_page=100&page={page}"
        batch = api_json(url, token)
        if not batch:
            break
        releases.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return [r for r in releases if not r.get("draft")]


def release_downloads(release: dict) -> int:
    """Total downloads across all assets of one release."""
    return sum(int(a.get("download_count") or 0) for a in release.get("assets") or [])


# --------------------------------------------------------------------------
# history
# --------------------------------------------------------------------------
def load_history(path: str) -> dict:
    if not os.path.exists(path):
        return {"schema": HISTORY_SCHEMA, "releases": {}, "snapshots": []}
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    data.setdefault("schema", HISTORY_SCHEMA)
    data.setdefault("releases", {})
    data.setdefault("snapshots", [])
    return data


def update_history(history: dict, releases: list[dict], repo: str, now: datetime) -> dict:
    today = now.date().isoformat()
    rel_state: dict = history["releases"]

    for rel in releases:
        tag = rel.get("tag_name")
        if not tag:
            continue
        entry = rel_state.setdefault(tag, {"published_at": None, "downloads": 0, "last_seen": None, "retired": False})
        entry["published_at"] = rel.get("published_at") or entry.get("published_at")
        entry["downloads"] = release_downloads(rel)
        entry["last_seen"] = today
        entry["retired"] = False

    # Releases pruned from the API keep their last known count (never reset, so
    # the total is monotonic) but are flagged as retired.
    live_tags = {r.get("tag_name") for r in releases}
    for tag, entry in rel_state.items():
        if tag not in live_tags:
            entry["retired"] = True

    total = sum(int(e.get("downloads") or 0) for e in rel_state.values())
    by_tag = {tag: int(e.get("downloads") or 0) for tag, e in rel_state.items() if not e.get("retired")}

    snapshots: list = history["snapshots"]
    if snapshots and snapshots[-1]["date"] == today:
        prev_total = snapshots[-2]["total"] if len(snapshots) > 1 else None
        snapshots[-1] = {
            "date": today,
            "total": total,
            "delta": (total - prev_total) if prev_total is not None else None,
            "by_tag": by_tag,
        }
    else:
        prev_total = snapshots[-1]["total"] if snapshots else None
        snapshots.append(
            {
                "date": today,
                "total": total,
                "delta": (total - prev_total) if prev_total is not None else None,
                "by_tag": by_tag,
            }
        )

    history["repo"] = repo
    history["schema"] = HISTORY_SCHEMA
    history["updated_at"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    history.setdefault("first_snapshot", snapshots[0]["date"] if snapshots else today)
    return history


def save_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False, sort_keys=False)
        fh.write("\n")


# --------------------------------------------------------------------------
# chart
# --------------------------------------------------------------------------
def fmt_count(n: float) -> str:
    n = float(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 1_000:
        return f"{n / 1_000:.1f}k".replace(".0k", "k")
    return str(int(n))


def nice_scale(vmax: int, ticks: int = 4) -> tuple[int, int]:
    """Return (step, top) for the Y axis so ticks land on round numbers."""
    if vmax <= 0:
        return 1, 1
    target = vmax / ticks
    mag = 10 ** math.floor(math.log10(target))
    step = mag
    for m in (1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        step = m * mag
        if step >= target:
            break
    step = max(1, int(round(step)))
    top = int(math.ceil(vmax / step) * step)
    return step, top


def esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_svg(history: dict, pal: dict, out_path: str) -> None:
    snapshots = history.get("snapshots") or []
    if not snapshots:
        return

    dates = [s["date"] for s in snapshots]
    values = [float(s["total"]) for s in snapshots]
    n = len(values)

    W, H = 860, 320
    pad_l, pad_r, pad_t, pad_b = 66, 30, 58, 44
    x0, x1 = pad_l, W - pad_r
    y0, y1 = pad_t, H - pad_b

    vmax = max(values) if values else 0
    step, top = nice_scale(int(vmax))
    ymax = max(top, 1)

    def px(i: int) -> float:
        if n == 1:
            return x0 + (x1 - x0) * 0.5
        return x0 + (x1 - x0) * i / (n - 1)

    def py(v: float) -> float:
        return y1 - (v / ymax) * (y1 - y0)

    pts = [(px(i), py(values[i])) for i in range(n)]
    latest = values[-1]

    # -- axis ticks ---------------------------------------------------------
    y_ticks = list(range(0, top + 1, step)) or [0, top]
    max_x_labels = 7
    if n == 1:
        x_idx = [0]
    else:
        stride = max(1, math.ceil((n - 1) / (max_x_labels - 1)))
        x_idx = list(range(0, n, stride))
        if x_idx[-1] != n - 1:
            x_idx.append(n - 1)

    parts: list[str] = []
    add = parts.append
    add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Total release downloads over time">')
    add(f'<defs><linearGradient id="fill" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{pal["line"]}" stop-opacity="{pal["area_opacity"]}"/>'
        f'<stop offset="100%" stop-color="{pal["line"]}" stop-opacity="0"/>'
        f'</linearGradient></defs>')
    add(f'<g font-family="-apple-system, BlinkMacSystemFont, \'Segoe UI\', \'Noto Sans\', Helvetica, Arial, sans-serif">')

    # -- grid ---------------------------------------------------------------
    for t in y_ticks:
        gy = py(t)
        add(f'<line x1="{x0}" y1="{gy:.1f}" x2="{x1}" y2="{gy:.1f}" stroke="{pal["grid"]}" stroke-width="1"/>')
        add(f'<text x="{x0 - 12}" y="{gy:.1f}" fill="{pal["muted"]}" font-size="11" text-anchor="end" dominant-baseline="middle">{fmt_count(t)}</text>')

    # -- area + line --------------------------------------------------------
    if n >= 2:
        area = [f"M {pts[0][0]:.1f} {y1:.1f}"]
        area += [f"L {x:.1f} {y:.1f}" for x, y in pts]
        area.append(f"L {pts[-1][0]:.1f} {y1:.1f} Z")
        add(f'<path d="{" ".join(area)}" fill="url(#fill)" stroke="none"/>')

        line = [f"M {pts[0][0]:.1f} {pts[0][1]:.1f}"]
        line += [f"L {x:.1f} {y:.1f}" for x, y in pts[1:]]
        add(f'<path d="{" ".join(line)}" fill="none" stroke="{pal["line"]}" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round"/>')

        if n <= 120:
            for x, y in pts[:-1]:
                add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.6" fill="{pal["line"]}"/>')

    # -- latest marker ------------------------------------------------------
    lx, ly = pts[-1]
    add(f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="5" fill="{pal["line"]}" stroke="{pal["dot_stroke"]}" stroke-width="2"/>')

    # -- baseline -----------------------------------------------------------
    add(f'<line x1="{x0}" y1="{y1:.1f}" x2="{x1}" y2="{y1:.1f}" stroke="{pal["axis"]}" stroke-width="1"/>')

    # -- x labels -----------------------------------------------------------
    for i in x_idx:
        add(f'<text x="{px(i):.1f}" y="{y1 + 22}" fill="{pal["muted"]}" font-size="11" text-anchor="middle">{dates[i][5:]}</text>')

    # -- header -------------------------------------------------------------
    first = dates[0]
    note = f"since {first}" if n >= 2 else f"tracking started {first}"
    add(f'<text x="{x0}" y="28" fill="{pal["muted"]}" font-size="13">Total release downloads'
        f'<tspan dx="10" font-size="11" opacity="0.75">· {esc(note)}</tspan></text>')
    add(f'<text x="{x1}" y="34" fill="{pal["text"]}" font-size="26" font-weight="600" text-anchor="end">{fmt_count(latest)}</text>')

    add("</g></svg>")

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(parts))
        fh.write("\n")


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Track GitHub release downloads and render an SVG chart.")
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"), help="owner/name (default: $GITHUB_REPOSITORY)")
    ap.add_argument("--assets-dir", default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets"))
    ap.add_argument("--history", default=None, help="override history file path")
    ap.add_argument("--offline", action="store_true", help="re-render the chart from the existing history only")
    args = ap.parse_args(argv)

    history_path = args.history or os.path.join(args.assets_dir, "downloads-history.json")
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

    history = load_history(history_path)
    now = datetime.now(timezone.utc)

    if not args.offline:
        if not args.repo:
            print("error: --repo or $GITHUB_REPOSITORY is required", file=sys.stderr)
            return 2
        try:
            releases = fetch_releases(args.repo, token)
        except urllib.error.HTTPError as exc:
            print(f"error: GitHub API returned {exc.code} {exc.reason}", file=sys.stderr)
            return 1
        except urllib.error.URLError as exc:
            print(f"error: cannot reach GitHub API: {exc.reason}", file=sys.stderr)
            return 1
        history = update_history(history, releases, args.repo, now)
        save_json(history_path, history)
        live = sum(1 for e in history["releases"].values() if not e.get("retired"))
        print(f"{len(releases)} live release(s), {live} tracked tag(s), total {history['snapshots'][-1]['total']}")

    render_svg(history, LIGHT, os.path.join(args.assets_dir, "downloads-chart.svg"))
    render_svg(history, DARK, os.path.join(args.assets_dir, "downloads-chart-dark.svg"))
    print(f"wrote {os.path.join(args.assets_dir, 'downloads-chart.svg')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
