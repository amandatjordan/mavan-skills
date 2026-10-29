#!/usr/bin/env python3
"""Service Page H1 & Title Tag Review.

  python build.py inspect --crawl export.csv --out work
  python build.py build   --crawl export.csv --gsc work/gsc --out review.xlsx

inspect: shows which export columns will be used and writes work/urls.txt (the crawled URLs, for the GSC filter).
build:   matches every page to the Service Taxonomy, builds each page's keyword pool, picks the top 5 by volume,
         merges the saved GSC rows, builds the three-tab workbook and runs the QA checks.
Every count, match and join happens here. Rules: references/rules.md.
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict
from urllib.parse import unquote, urlsplit

import pandas as pd
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_TAXONOMY = os.path.join(SKILL, "references", "service-taxonomy.xlsx")

URL_NAMES = ["address", "url", "page url"]
H1_NAMES = ["h1-1", "h1", "h1 1"]
TITLE_NAMES = ["title 1", "title", "page title"]

CORE_LEVELS = ["Brand / Device", "Sub-Service", "Service"]  # most specific first
NO_FLAG = re.compile(r"do not flag|not us-approved", re.I)


# ---------------------------------------------------------------- crawl / urls

def read_table(path):
    if path.lower().endswith((".xlsx", ".xlsm")):
        return pd.read_excel(path, dtype=str).fillna("")
    return pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig", encoding_errors="replace")


def find_col(df, override, names, label):
    lookup = {c.strip().lower(): c for c in df.columns}
    if override:
        if override.strip().lower() not in lookup:
            sys.exit(f"--{label}-col '{override}' is not a column. Columns: {list(df.columns)}")
        return lookup[override.strip().lower()]
    for n in names:
        if n in lookup:
            return lookup[n]
    sys.exit(f"Could not find the {label} column. Columns: {list(df.columns)}. Re-run with --{label}-col NAME.")


def norm_url(u):
    u = u.strip()
    if not re.match(r"^[a-z][a-z0-9+.-]*://", u, re.I):
        u = "//" + u
    p = urlsplit(u)
    path = unquote(p.path or "/")
    if len(path) > 1:
        path = path.rstrip("/")
    return (p.netloc.lower() + path).lower()


def page_path(u):
    p = urlsplit(u.strip())
    return unquote(p.path) or "/"


def load_crawl(args):
    df = read_table(args.crawl)
    cu = find_col(df, args.url_col, URL_NAMES, "url")
    ch = find_col(df, args.h1_col, H1_NAMES, "h1")
    ct = find_col(df, args.title_col, TITLE_NAMES, "title")
    pages, seen, dups = [], set(), 0
    for _, r in df.iterrows():
        url = r[cu].strip()
        if not url:
            continue
        key = norm_url(url)
        if key in seen:
            dups += 1
            continue
        seen.add(key)
        pages.append({"url": url, "key": key, "path": page_path(url), "h1": r[ch].strip(), "title": r[ct].strip()})
    return pages, (cu, ch, ct), dups


# ------------------------------------------------------------------------ gsc

def collect_rows(obj, out):
    """Find every {clicks, impressions, page url} row in any JSON wrapper."""
    if isinstance(obj, str):
        s = obj.strip()
        if s[:1] in "[{":
            try:
                collect_rows(json.loads(s), out)
            except ValueError:
                pass
    elif isinstance(obj, dict):
        if "clicks" in obj and "impressions" in obj:
            url = None
            keys = obj.get("keys")
            if isinstance(keys, list) and keys and isinstance(keys[0], str):
                url = keys[0]
            for k in ("page", "url", "Page", "URL"):
                if url is None and isinstance(obj.get(k), str):
                    url = obj[k]
            if url:
                out.append((url, float(obj["clicks"]), float(obj["impressions"])))
            return
        for v in obj.values():
            collect_rows(v, out)
    elif isinstance(obj, list):
        for v in obj:
            collect_rows(v, out)


def load_gsc(path):
    files = []
    if os.path.isdir(path):
        files = sorted(os.path.join(path, f) for f in os.listdir(path) if f.lower().endswith((".json", ".csv")))
    elif os.path.isfile(path):
        files = [path]
    if not files:
        sys.exit(f"No .json or .csv GSC files found at {path}")
    total = {}
    for f in files:
        rows = []
        if f.lower().endswith(".json"):
            with open(f, encoding="utf-8") as fh:
                collect_rows(json.load(fh), rows)
        else:
            df = read_table(f)
            lk = {c.strip().lower(): c for c in df.columns}
            cu = next((lk[n] for n in ("url", "page", "address") if n in lk), None)
            if not cu or "clicks" not in lk or "impressions" not in lk:
                sys.exit(f"{f}: needs url (or page), clicks and impressions columns. Columns: {list(df.columns)}")
            for _, r in df.iterrows():
                rows.append((r[cu], float(r[lk['clicks']] or 0), float(r[lk['impressions']] or 0)))
        print(f"  GSC file {os.path.basename(f)}: {len(rows)} rows")
        if not rows:
            sys.exit(f"{f}: 0 rows read. Stop and show the person the response shape; do not guess a format.")
        for url, c, i in rows:
            k = norm_url(url)
            cc, ii = total.get(k, (0, 0))
            total[k] = (cc + c, ii + i)
    return total


# ------------------------------------------------------------------- taxonomy

class Entry:
    def __init__(self, level, service, sub, brand, concern, implies, status, rx):
        self.level, self.service, self.sub, self.brand, self.concern = level, service, sub, brand, concern
        self.implies = [n.strip() for n in implies.split(";") if n.strip()]
        self.status, self.rx = status, rx
        self.name = {"Service": service, "Sub-Service": sub, "Brand / Device": brand, "Concern": concern}[level]
        self.key = (level, service if level != "Concern" else "", self.name)
        self.label = {"Service": self.name, "Concern": f"{self.name} (Concern)"}.get(level, f"{self.name} ({service})")

    def blocked(self):
        return bool(NO_FLAG.search(self.status))


def load_taxonomy(path):
    tax = pd.read_excel(path, sheet_name="Taxonomy", dtype=str).fillna("")
    tax.columns = [c.strip() for c in tax.columns]
    entries, bad = [], []
    for _, r in tax.iterrows():
        lvl = r["Level"].strip()
        if lvl not in CORE_LEVELS + ["Concern"]:
            continue
        pat = r["Match Terms (regex)"].strip()
        try:
            rx = re.compile(pat, re.I) if pat else None
        except re.error:
            bad.append(pat)
            rx = None
        entries.append(Entry(lvl, r["Service"].strip(), r["Sub-Service"].strip(), r["Brand / Device"].strip(),
                             r["Concern"].strip(), r["Implies Offered"], r["Status / Notes"], rx))
    if bad:
        print(f"WARNING: {len(bad)} match terms are not valid Python regex and were skipped: {bad[:3]}")
    kw = pd.read_excel(path, sheet_name="All Keywords", dtype=str).fillna("")
    kw.columns = [c.strip() for c in kw.columns]
    base = next(c for c in kw.columns if c.startswith("Base Term"))
    kw["Volume"] = pd.to_numeric(kw["Volume"].str.replace(",", ""), errors="coerce").fillna(0).astype(int)
    pools = defaultdict(list)
    cols = {c: i for i, c in enumerate(kw.columns)}
    for row in kw.itertuples(index=False, name=None):
        cls, ml = row[cols["Class"]], row[cols["Matched Level"]]
        item = (row[cols["Keyword"]], row[cols[base]], row[cols["Volume"]])
        svc, sub, brand, con = (row[cols[c]] for c in ("Service", "Sub-Service", "Brand / Device", "Concern"))
        if cls == "Service" and ml == "Service":
            pools[("Service", svc, svc)].append(item)
        elif cls == "Service" and ml == "Sub-Service":
            pools[("Sub-Service", svc, sub)].append(item)
        elif cls == "Service" and ml == "Brand / Device":
            pools[("Brand / Device", svc, brand)].append(item)
        elif cls == "Concern":
            pools[("Concern", "", con)].append(item)
    return entries, pools


def page_texts(p):
    path = re.sub(r"[-_/.+]+", " ", p["path"].lower()).strip()
    title = p["title"].split("|")[0].strip().lower()
    return [("path", path), ("H1", p["h1"].lower()), ("title", title)]


def resolve_page(p, entries):
    """Return (entry or None, matched field, review reason)."""
    texts = page_texts(p)

    def hits(text, levels):
        """level -> {entry key: (longest matched text, entry)}"""
        found = {}
        for e in entries:
            if e.level in levels and e.rx and text:
                spans = [m.group() for m in e.rx.finditer(text) if m.group()]
                if spans:
                    found.setdefault(e.level, {})[e.key] = (max(spans, key=len), e)
        return found

    def narrow(cands):
        """Drop the broader of two matching entries; what is left is a true tie."""
        keep = []
        for text_a, a in cands:
            broader = False
            for text_b, b in cands:
                if a is b:
                    continue
                if a.implies and set(a.implies) < set(b.implies):  # b implies everything a does, and more
                    broader = True
                elif len(text_b) > len(text_a) and text_a in text_b:  # a's match is only part of b's match
                    broader = True
            if not broader:
                keep.append(a)
        return keep or [e for _, e in cands]  # the two rules contradict each other: leave it to a person

    for levels in (CORE_LEVELS, ["Concern"]):  # Concerns only when nothing else matches in any field
        for field, text in texts:
            found = hits(text, levels)
            for lvl in levels:
                if found.get(lvl):
                    top = narrow(list(found[lvl].values()))
                    if len(top) == 1:
                        return top[0], field, ""
                    names = "; ".join(sorted(e.label for e in top))
                    return None, field, f"Needs review: {len(top)} {lvl} entries match ({names})"
    return None, "", "Needs review: no taxonomy match"


def implied_entries(entry, entries):
    """Entries named in Implies Offered. Returns (found, unresolved names)."""
    svc = {e.service: e for e in entries if e.level == "Service"}
    subs = defaultdict(list)
    for e in entries:
        if e.level == "Sub-Service":
            subs[e.sub].append(e)
    found, missing = [], []
    for n in entry.implies:
        if entry.level == "Concern":
            cands = subs.get(n, []) + ([svc[n]] if n in svc else [])
        elif n == entry.service and n in svc:
            cands = [svc[n]]
        else:
            cands = [s for s in subs.get(n, []) if s.service == entry.service]
        cands = [c for c in cands if c.key != entry.key]
        if cands:
            found.extend(cands)
        else:
            missing.append(n)
    return found, missing


# ------------------------------------------------------------------- keywords

def dedupe_key(term):
    k = re.sub(r"[\s\-]+", "", term.lower())
    return k[:-1] if len(k) > 3 and k.endswith("s") else k


def top5(items):
    best = {}
    for kwd, base, vol in items:
        term = (base or kwd).strip()
        k = dedupe_key(term)
        cand = (-vol, len(term), term)
        if k not in best or cand < best[k]:
            best[k] = cand
    ranked = sorted(best.values())[:5]
    return [(t, -v) for v, _, t in ranked]


# ------------------------------------------------------------------- workbook

ARIAL = Font(name="Arial", size=10)
HEAD = Font(name="Arial", size=10, bold=True, color="FFFFFF")
HEAD_FILL = PatternFill("solid", fgColor="1F3864")
YELLOW = PatternFill("solid", fgColor="FFF2CC")


def add_sheet(wb, first, title, headers, rows, widths, numeric=(), yellow=(), name=None):
    ws = wb.active if first else wb.create_sheet()
    ws.title = title
    ws.append(headers)
    for r in rows:
        ws.append(r)
    for c, h in enumerate(headers, 1):
        cell = ws.cell(1, c)
        cell.font, cell.fill = HEAD, (YELLOW if h in yellow else HEAD_FILL)
        if h in yellow:
            cell.font = Font(name="Arial", size=10, bold=True)
        cell.alignment = Alignment(vertical="top", wrap_text=True)
        ws.column_dimensions[get_column_letter(c)].width = widths[c - 1]
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.font = ARIAL
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            if headers[cell.column - 1] in numeric:
                cell.number_format = "#,##0"
            if headers[cell.column - 1] in yellow:
                cell.fill = YELLOW
    ws.freeze_panes = "A2"
    ref = f"A1:{get_column_letter(len(headers))}{len(rows) + 1}"
    t = Table(displayName=name or title.replace(" ", ""), ref=ref)
    t.tableStyleInfo = TableStyleInfo(name="TableStyleLight1", showRowStripes=False)
    ws.add_table(t)
    return ws


# ----------------------------------------------------------------------- main

def cmd_inspect(args):
    pages, cols, dups = load_crawl(args)
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "urls.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(p["url"] for p in pages) + "\n")
    print(f"Columns used: URL='{cols[0]}', H1='{cols[1]}', Title='{cols[2]}'")
    print(f"Pages: {len(pages)} (duplicate URLs skipped: {dups}); blank H1: {sum(not p['h1'] for p in pages)}; "
          f"blank title: {sum(not p['title'] for p in pages)}")
    for p in pages[:3]:
        print(f"  {p['url']} | {p['h1'][:50]} | {p['title'][:50]}")
    print(f"Wrote {os.path.join(args.out, 'urls.txt')}")


def cmd_build(args):
    pages, cols, dups = load_crawl(args)
    entries, pools = load_taxonomy(args.taxonomy)
    gsc = load_gsc(args.gsc)
    print(f"Pages: {len(pages)} (duplicates skipped {dups}); taxonomy entries: {len(entries)}")

    # 1. match each page to one taxonomy entry
    for p in pages:
        p["entry"], p["field"], p["reason"] = resolve_page(p, entries)
    has_page = {p["entry"].key for p in pages if p["entry"]}

    # 2. keyword pool: own entry, plus implied entries that have no page in the crawl
    recs = {}
    unresolved = defaultdict(set)
    for p in pages:
        p["notes"], p["lines"] = [], []
        e = p["entry"]
        if not e:
            p["notes"].append(p["reason"])
            continue
        items = list(pools.get(e.key, []))
        found, missing = implied_entries(e, entries)
        for n in missing:
            unresolved[n].add(e.label)
        added = []
        for imp in found:
            if imp.key in has_page or imp.blocked():
                continue
            items += pools.get(imp.key, [])
            added.append(imp.label)
            if e.level != "Concern":  # a Concern never proves the service is offered
                r = recs.setdefault(imp.key, {"entry": imp, "by": {}})
                r["by"][p["url"]] = e.label
        p["notes"].append(f"Matched on {p['field']}")
        if added:
            p["notes"].append("Also used keywords of entries with no page in the crawl: " + "; ".join(added))
        p["lines"] = top5(items)
        if not p["lines"]:
            p["notes"].append("No keywords found in taxonomy")

    # 3. merge GSC
    matched_gsc = 0
    for p in pages:
        g = gsc.get(p["key"])
        p["clicks"], p["impr"] = (int(g[0]), int(g[1])) if g else (0, 0)
        if g:
            matched_gsc += 1
        else:
            p["notes"].append("No GSC data")
        if not p["h1"]:
            p["notes"].append("Blank H1")
        if not p["title"]:
            p["notes"].append("Blank Title Tag")
    rate = matched_gsc / len(pages) if pages else 0
    crawl_keys = {p["key"] for p in pages}
    extra = sum(1 for k in gsc if k not in crawl_keys)
    print(f"GSC rows matched to crawled pages: {matched_gsc}/{len(pages)} ({rate:.0%}); GSC rows not in crawl: {extra}")
    if rate < 0.5:
        print("WARNING: under half the pages matched a GSC row. Check the property, the date range and the URL form "
              "(http/https, www, trailing slash) before trusting the metrics.")

    # 4. workbook
    review = []
    for p in sorted(pages, key=lambda x: (-x["clicks"], -x["impr"], x["url"])):
        e = p["entry"]
        review.append([p["url"], f"{e.level}: {e.label}" if e else "Needs review", p["title"], p["h1"], None, None,
                       "\n".join(f"{t} - {v:,}" for t, v in p["lines"]), p["clicks"], p["impr"],
                       " | ".join(p["notes"])])
    rec_rows = []
    order = {"Service": 0, "Sub-Service": 1, "Brand / Device": 2}
    for r in sorted(recs.values(), key=lambda r: (order[r["entry"].level], r["entry"].label)):
        labels = sorted(set(r["by"].values()))
        rec_rows.append([r["entry"].label, r["entry"].level, "\n".join(r["by"]),
                         f"Implied by the {', '.join(labels)} page; no crawled page maps to {r['entry'].label}."])
    if not rec_rows:
        rec_rows = [["None", "", "", "No implied page is missing from the crawl."]]
    data = [[p["url"], p["path"], p["h1"], p["title"], p["clicks"], p["impr"]] for p in pages]

    wb = Workbook()
    ws = add_sheet(wb, True, "Review",
                   ["URL", "Matched Taxonomy Entry", "Current Page Title", "Current H1", "Suggested Page Title",
                    "Suggested H1", "Update to Include", "GSC Clicks", "GSC Impressions", "Notes"],
                   review, [45, 30, 40, 36, 40, 36, 38, 11, 13, 45],
                   numeric=("GSC Clicks", "GSC Impressions"), yellow=("Suggested Page Title", "Suggested H1"))
    ws["G1"].comment = Comment("Volume comes from competitor rankings, often in other markets. Use it to rank "
                               "keywords against each other, not as demand for this client.", "Mavan")
    add_sheet(wb, False, "Recommendations", ["Recommended Page", "Level", "Implied By (URL)", "Reason"],
              rec_rows, [38, 16, 55, 70])
    add_sheet(wb, False, "Data", ["URL", "Page Path", "H1", "Title Tag", "GSC Clicks", "GSC Impressions"],
              data, [45, 36, 36, 40, 11, 13], numeric=("GSC Clicks", "GSC Impressions"))
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    wb.save(args.out)
    print(f"Saved {args.out}")

    # 5. summary and QA
    by_level = defaultdict(int)
    for p in pages:
        by_level[p["entry"].level if p["entry"] else "Needs review"] += 1
    print("Pages by matched level:", dict(by_level))
    reasons = defaultdict(int)
    for p in pages:
        if not p["entry"]:
            reasons[p["reason"]] += 1
    for r, n in reasons.items():
        print(f"  {n} x {r}")
    real_recs = [r for r in rec_rows if r[0] != "None"]
    print(f"Recommendations: {len(real_recs)}")
    for n, labels in unresolved.items():
        print(f"Implies Offered name not found in the Taxonomy tab: '{n}' (named on: {', '.join(sorted(labels))})")

    checks = []
    checks.append(("Every crawled URL once in Data and once in Review",
                   len(data) == len(review) == len(crawl_keys) and {norm_url(r[0]) for r in review} == crawl_keys))
    ok = True
    for p in pages:
        vols = [v for _, v in p["lines"]]
        keys = [dedupe_key(t) for t, _ in p["lines"]]
        if len(vols) > 5 or vols != sorted(vols, reverse=True) or len(keys) != len(set(keys)):
            ok = False
    checks.append(("Update to Include: at most 5 lines, highest volume first, no duplicates", ok))
    checks.append(("Needs review rows have no keywords", all(not p["lines"] for p in pages if not p["entry"])))
    checks.append(("Every Recommendations row names crawled URLs",
                   all(norm_url(u) in crawl_keys for r in recs.values() for u in r["by"])))
    failed = False
    for name, passed in checks:
        print(("PASS  " if passed else "FAIL  ") + name)
        failed |= not passed
    sys.exit(1 if failed else 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("inspect", "build"):
        sp = sub.add_parser(name)
        sp.add_argument("--crawl", required=True, help="Screaming Frog or Sitebulb export (CSV or xlsx)")
        sp.add_argument("--url-col")
        sp.add_argument("--h1-col")
        sp.add_argument("--title-col")
        sp.add_argument("--out", required=True, help="inspect: work folder. build: output .xlsx path")
        if name == "build":
            sp.add_argument("--gsc", required=True, help="folder (or file) of saved GSC rows, .json or .csv")
            sp.add_argument("--taxonomy", default=DEFAULT_TAXONOMY)
    args = ap.parse_args()
    cmd_inspect(args) if args.cmd == "inspect" else cmd_build(args)


if __name__ == "__main__":
    main()
