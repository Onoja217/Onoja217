#!/usr/bin/env python3
"""Generate self-hosted GitHub profile statistics SVGs using the GitHub GraphQL API."""
import datetime as dt
import html
import json
import os
import pathlib
import urllib.request

USERNAME = os.environ.get("GITHUB_USERNAME", "Onoja217")
TOKEN = os.environ["GITHUB_TOKEN"]
OUT = pathlib.Path("stats")
OUT.mkdir(exist_ok=True)
ACCENT = "#38BDF8"
TEXT = "#CBD5E1"
MUTED = "#94A3B8"
BG = "#0B1220"
BORDER = "#263449"

def api(query):
    body = json.dumps({"query": query}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql", data=body,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        payload = json.load(response)
    if payload.get("errors"):
        raise RuntimeError(payload["errors"])
    return payload["data"]

today = dt.datetime.now(dt.timezone.utc).date()
since = today - dt.timedelta(days=365)
query = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC) {
      totalCount
      nodes { stargazerCount languages(first: 10, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name } } } }
    }
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { contributionCount date } }
      }
    }
  }
}
"""
variables = {
    "login": USERNAME,
    "from": dt.datetime.combine(since, dt.time.min, dt.timezone.utc).isoformat(),
    "to": dt.datetime.combine(today, dt.time.max, dt.timezone.utc).isoformat(),
}
body = json.dumps({"query": query, "variables": variables}).encode()
req = urllib.request.Request(
    "https://api.github.com/graphql", data=body,
    headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
)
with urllib.request.urlopen(req, timeout=30) as response:
    payload = json.load(response)
if payload.get("errors"):
    raise RuntimeError(payload["errors"])
user = payload["data"]["user"]
if not user:
    raise RuntimeError(f"GitHub user {USERNAME} was not found")

repos = user["repositories"]
collection = user["contributionsCollection"]
calendar = collection["contributionCalendar"]
days = [day for week in calendar["weeks"] for day in week["contributionDays"]]
counts = [d["contributionCount"] for d in days]
stars = sum(repo["stargazerCount"] for repo in repos["nodes"])
commits = collection["totalCommitContributions"]
prs = collection["totalPullRequestContributions"]
issues = collection["totalIssueContributions"]
total = calendar["totalContributions"]

# Calculate current and longest contribution streaks from the calendar.
longest = current = run = 0
for count in counts:
    run = run + 1 if count else 0
    longest = max(longest, run)
    current = run
if days and days[-1]["contributionCount"] == 0 and len(days) > 1 and days[-2]["contributionCount"] > 0:
    current = 0
elif days and days[-1]["contributionCount"] == 0:
    current = 0
# Calendar includes today; if no contribution today, yesterday can still be an active streak.
if days and days[-1]["contributionCount"] == 0 and len(days) > 1:
    run = 0
    for d in reversed(days[:-1]):
        if d["contributionCount"]:
            run += 1
        else:
            break
    current = run

def svg_start(width, height, title):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">',
            '<defs><linearGradient id="accent" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#0EA5E9"/><stop offset="1" stop-color="#38BDF8"/></linearGradient></defs>',
            f'<rect width="{width}" height="{height}" rx="14" fill="{BG}" stroke="{BORDER}"/>']

def txt(x, y, value, size=13, color=TEXT, weight=400):
    return f'<text x="{x}" y="{y}" fill="{color}" font-family="Segoe UI,Arial,sans-serif" font-size="{size}" font-weight="{weight}">{html.escape(str(value))}</text>'

# Overview card
s = svg_start(495, 190, "GitHub statistics")
s += [txt(24, 34, f"{USERNAME} · GitHub Statistics", 17, TEXT, 700),
      txt(24, 56, "Public repositories and contributions · last 12 months", 11, MUTED)]
metrics = [("Repositories", repos["totalCount"]), ("Stars earned", stars),
           ("Commits", commits), ("Pull requests", prs), ("Issues", issues),
           ("Contributions", total)]
for i, (label, value) in enumerate(metrics):
    x = 26 + (i % 3) * 158
    y = 100 + (i // 3) * 66
    s += [txt(x, y, f"{value:,}", 23, ACCENT, 700), txt(x, y + 20, label, 11, MUTED)]
s.append("</svg>")
(OUT / "github-stats.svg").write_text("\n".join(s), encoding="utf-8")

# Language distribution card (repository code size, not proficiency).
language_sizes = {}
for repo in repos["nodes"]:
    for edge in repo["languages"]["edges"]:
        name = edge["node"]["name"]
        language_sizes[name] = language_sizes.get(name, 0) + edge["size"]
top = sorted(language_sizes.items(), key=lambda item: item[1], reverse=True)[:6]
s = svg_start(495, 220, "Most used programming languages")
s += [txt(24, 34, "Most Used Languages", 17, TEXT, 700),
      txt(24, 55, "Aggregated from public repository code size", 11, MUTED)]
palette = ["#38BDF8", "#A78BFA", "#34D399", "#FBBF24", "#FB7185", "#60A5FA"]
grand = sum(language_sizes.values()) or 1
bar_x, bar_y, bar_w, bar_h = 24, 75, 447, 10
cursor = bar_x
for i, (name, size) in enumerate(top):
    width = bar_w * size / grand
    s.append(f'<rect x="{cursor:.1f}" y="{bar_y}" width="{max(width, 1):.1f}" height="{bar_h}" rx="4" fill="{palette[i % len(palette)]}"/>')
    cursor += width
for i, (name, size) in enumerate(top):
    col, row = i % 2, i // 2
    x, y = 26 + col * 230, 116 + row * 31
    pct = size / grand * 100
    s += [f'<circle cx="{x}" cy="{y-4}" r="4" fill="{palette[i % len(palette)]}"/>',
          txt(x + 12, y, name, 12, TEXT, 600),
          f'<text x="{x+205}" y="{y}" text-anchor="end" fill="{MUTED}" font-family="Segoe UI,Arial,sans-serif" font-size="11">{pct:.1f}%</text>']
if not top:
    s.append(txt(24, 115, "No public language data available yet.", 12, MUTED))
s.append("</svg>")
(OUT / "top-languages.svg").write_text("\n".join(s), encoding="utf-8")

# Contribution consistency card.
s = svg_start(495, 150, "GitHub contribution streak")
s += [txt(24, 34, "Contribution Consistency", 17, TEXT, 700),
      txt(24, 57, f"{current} day current streak", 22, ACCENT, 700),
      txt(260, 57, f"{longest} day longest streak", 22, TEXT, 700),
      txt(24, 91, f"{total:,} contributions in the last 12 months", 12, MUTED),
      txt(24, 119, "Based on GitHub's public contribution calendar", 10, MUTED),
      "</svg>"]
(OUT / "contribution-streak.svg").write_text("\n".join(s), encoding="utf-8")

# Contribution activity heatmap / graph.
width, height = 900, 190
s = svg_start(width, height, "GitHub contribution activity graph")
s += [txt(22, 28, "Contribution Activity · Last 12 Months", 15, TEXT, 700)]
start_x, start_y, cell, gap = 24, 48, 10, 3
max_count = max(counts) if counts else 1
for idx, day in enumerate(days):
    x = start_x + idx // 7 * (cell + gap)
    y = start_y + idx % 7 * (cell + gap)
    n = day["contributionCount"]
    level = 0 if n == 0 else min(4, 1 + int((n / max_count) * 3))
    fills = ["#172334", "#075985", "#0E7490", "#0284C7", "#38BDF8"]
    s.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{fills[level]}"><title>{day["date"]}: {n} contributions</title></rect>')
s += [txt(24, 174, f"{total:,} contributions", 10, MUTED),
      txt(760, 174, "Less", 10, MUTED)]
for i, fill in enumerate(["#172334", "#075985", "#0E7490", "#0284C7", "#38BDF8"]):
    s.append(f'<rect x="{795+i*16}" y="165" width="10" height="10" rx="2" fill="{fill}"/>')
s += [txt(884, 174, "More", 10, MUTED), "</svg>"]
(OUT / "activity-graph.svg").write_text("\n".join(s), encoding="utf-8")

print(f"Generated 4 SVG cards for {USERNAME}: {total} contributions, {repos['totalCount']} public repositories.")
