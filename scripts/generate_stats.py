#!/usr/bin/env python3
"""Generate assets/stats.svg and assets/commits-30d.svg from the GitHub GraphQL API.
Needs env GH_TOKEN (PAT with `repo` + `read:user`) so private-repo commits are counted.
Stdlib only."""
import os, json, datetime as dt, urllib.request

TOKEN = os.environ["GH_TOKEN"]
LOGIN = os.environ.get("GH_LOGIN", "iamrahulmeena")
OUT = os.environ.get("OUT_DIR", "assets")
os.makedirs(OUT, exist_ok=True)

BG, CARD, TXT, MUTED, ACC, ACC2, EMPTY = "#0d1117", "#161b22", "#e6edf3", "#8b949e", "#7F3FBF", "#c084fc", "#2d333b"
FONT = "font-family='JetBrains Mono,Consolas,monospace'"


def gql(q):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": q}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json", "User-Agent": "profile-stats"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.load(r)
    if "errors" in d:
        raise SystemExit(d["errors"])
    return d["data"]


now = dt.datetime.now(dt.timezone.utc)
created = gql('{user(login:"%s"){createdAt}}' % LOGIN)["user"]["createdAt"]
first_year = int(created[:4])

fields = """totalCommitContributions totalPullRequestContributions totalIssueContributions
 totalPullRequestReviewContributions restrictedContributionsCount
 contributionCalendar{weeks{contributionDays{date contributionCount}}}"""
parts = []
for y in range(first_year, now.year + 1):
    frm = f"{y}-01-01T00:00:00Z"
    to = min(dt.datetime(y, 12, 31, 23, 59, 59, tzinfo=dt.timezone.utc), now).strftime("%Y-%m-%dT%H:%M:%SZ")
    parts.append(f'y{y}: contributionsCollection(from:"{frm}", to:"{to}"){{{fields}}}')
data = gql('{user(login:"%s"){%s}}' % (LOGIN, " ".join(parts)))["user"]

days, commits_total, commits_year, prs, issues, reviews, restricted = {}, 0, 0, 0, 0, 0, 0
for y in range(first_year, now.year + 1):
    c = data[f"y{y}"]
    commits_total += c["totalCommitContributions"]
    prs += c["totalPullRequestContributions"]
    issues += c["totalIssueContributions"]
    reviews += c["totalPullRequestReviewContributions"]
    restricted += c["restrictedContributionsCount"]
    if y == now.year:
        commits_year = c["totalCommitContributions"]
    for w in c["contributionCalendar"]["weeks"]:
        for d in w["contributionDays"]:
            days[d["date"]] = d["contributionCount"]

today = now.date()
last30 = [today - dt.timedelta(days=i) for i in range(29, -1, -1)]
counts = [days.get(d.isoformat(), 0) for d in last30]

# streaks
cur, longest, run = 0, 0, 0
for d in sorted(days):
    run = run + 1 if days[d] > 0 else 0
    longest = max(longest, run)
d = today if days.get(today.isoformat(), 0) > 0 else today - dt.timedelta(days=1)
while days.get(d.isoformat(), 0) > 0:
    cur += 1
    d -= dt.timedelta(days=1)

print(f"commits_total={commits_total} year={commits_year} restricted_hidden={restricted} streak={cur}/{longest}")
if restricted:
    print("NOTE: restricted contributions present - token may lack `repo` scope, private commits could be undercounted.")

# ---------- stats card ----------
tiles = [
    ("TOTAL COMMITS", f"{commits_total:,}", "all time, incl. private"),
    (f"COMMITS {now.year}", f"{commits_year:,}", "this year"),
    ("LAST 30 DAYS", f"{sum(counts):,}", "contributions"),
    ("CURRENT STREAK", f"{cur}d", f"longest {longest}d"),
    ("PRs / REVIEWS", f"{prs} / {reviews}", f"{issues} issues"),
]
W, H, pad = 820, 130, 12
tw = (W - pad * (len(tiles) + 1)) / len(tiles)
svg = [f"<svg xmlns='http://www.w3.org/2000/svg' width='{W}' height='{H}' viewBox='0 0 {W} {H}'>",
       f"<rect width='{W}' height='{H}' rx='12' fill='{BG}'/>"]
for i, (lab, val, sub) in enumerate(tiles):
    x = pad + i * (tw + pad)
    svg.append(f"<rect x='{x:.1f}' y='{pad}' width='{tw:.1f}' height='{H-2*pad}' rx='10' fill='{CARD}'/>")
    svg.append(f"<rect x='{x:.1f}' y='{pad}' width='4' height='{H-2*pad}' rx='2' fill='{ACC}'/>")
    cx = x + tw / 2
    svg.append(f"<text x='{cx:.1f}' y='42' text-anchor='middle' fill='{MUTED}' font-size='10' {FONT}>{lab}</text>")
    svg.append(f"<text x='{cx:.1f}' y='74' text-anchor='middle' fill='{TXT}' font-size='26' font-weight='700' {FONT}>{val}</text>")
    svg.append(f"<text x='{cx:.1f}' y='98' text-anchor='middle' fill='{ACC2}' font-size='10' {FONT}>{sub}</text>")
svg.append("</svg>")
open(f"{OUT}/stats.svg", "w").write("\n".join(svg))

# ---------- 30-day bar chart ----------
W, H = 820, 270
L, R, T, B = 44, 20, 62, 42
pw, ph = W - L - R, H - T - B
step = pw / 30
bw = step - 5
peak = max(counts)
ymax = max(4, ((peak + 3) // 4) * 4)
pk_i = counts.index(peak) if peak else -1
svg = [f"<svg xmlns='http://www.w3.org/2000/svg' width='{W}' height='{H}' viewBox='0 0 {W} {H}'>",
       f"<rect width='{W}' height='{H}' rx='12' fill='{BG}'/>",
       f"<text x='{L}' y='28' fill='{TXT}' font-size='15' font-weight='700' {FONT}>Contributions - last 30 days</text>",
       f"<text x='{L}' y='46' fill='{MUTED}' font-size='11' {FONT}>total {sum(counts)}  |  avg {sum(counts)/30:.1f}/day  |  "
       f"peak {peak} on {last30[pk_i].strftime('%d %b') if peak else '-'}  |  active {sum(1 for c in counts if c)}/30 days</text>"]
for g in range(5):
    v = ymax * g / 4
    y = T + ph - ph * g / 4
    svg.append(f"<line x1='{L}' y1='{y:.1f}' x2='{W-R}' y2='{y:.1f}' stroke='{EMPTY}' stroke-width='1' stroke-dasharray='3 4'/>")
    svg.append(f"<text x='{L-8}' y='{y+4:.1f}' text-anchor='end' fill='{MUTED}' font-size='10' {FONT}>{v:g}</text>")
for i, (d, c) in enumerate(zip(last30, counts)):
    x = L + i * step + 2.5
    h = max(ph * c / ymax, 2)
    y = T + ph - h
    fill = ACC2 if i == pk_i and c else (ACC if c else EMPTY)
    svg.append(f"<rect x='{x:.1f}' y='{y:.1f}' width='{bw:.1f}' height='{h:.1f}' rx='3' fill='{fill}'><title>{d.isoformat()}: {c}</title></rect>")
    if c:
        svg.append(f"<text x='{x+bw/2:.1f}' y='{y-4:.1f}' text-anchor='middle' fill='{TXT if i==pk_i else MUTED}' font-size='9' {FONT}>{c}</text>")
    if i % 5 == 0 or i == 29:
        svg.append(f"<text x='{x+bw/2:.1f}' y='{H-20}' text-anchor='middle' fill='{MUTED}' font-size='10' {FONT}>{d.strftime('%d %b')}</text>")
svg.append("</svg>")
open(f"{OUT}/commits-30d.svg", "w").write("\n".join(svg))
