#!/usr/bin/env python3
"""Service Page H1 & Title Tag Review.

  python build.py inspect --crawl export.csv --out work
  python build.py build   --crawl export.csv --keywords work/keywords.tsv --out review.xlsx
                          [--recs work/recommendations.tsv] [--gsc work/gsc] [--cities "City, City"]

inspect: shows which export columns are used, writes work/urls.txt (for the Search Console filter) and
         work/pages.tsv (one compact line per page, for the AI to read).
build:   takes the AI's topic and target keywords for every page, ranks them by Search Console impressions when
         --gsc is given (otherwise keeps the AI's order and shows no numbers), flags the pages a person should
         review, builds the three-tab workbook and runs the QA checks.
The AI decides what each page is about and which keywords it should target. Every number, count and join happens
here; the AI never types a number. Rules: references/rules.md.
"""
import argparse
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict
from urllib.parse import unquote, urlsplit

import pandas as pd
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

URL_NAMES = ["address", "url", "page url"]
H1_NAMES = ["h1-1", "h1", "h1 1"]
TITLE_NAMES = ["title 1", "title", "page title"]
MAX_KEYWORDS = 8   # the AI proposes at most this many per page
STOP = {"and", "or", "in", "for", "of", "the", "a", "an", "to", "with", "near", "me", "by", "vs"}


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
    """Find every {clicks, impressions, page + query} row in any JSON wrapper."""
    if isinstance(obj, str):
        s = obj.strip()
        if s[:1] in "[{":
            try:
                collect_rows(json.loads(s), out)
            except ValueError:
                pass
    elif isinstance(obj, dict):
        if "clicks" in obj and "impressions" in obj:
            url = query = None
            keys = obj.get("keys")
            if isinstance(keys, list) and keys and isinstance(keys[0], str):
                url = keys[0]
                query = keys[1] if len(keys) > 1 and isinstance(keys[1], str) else None
            for k in ("page", "url", "Page", "URL"):
                if url is None and isinstance(obj.get(k), str):
                    url = obj[k]
            for k in ("query", "Query", "top queries"):
                if query is None and isinstance(obj.get(k), str):
                    query = obj[k]
            if url:
                out.append((url, query, float(obj["clicks"]), float(obj["impressions"])))
            return
        for v in obj.values():
            collect_rows(v, out)
    elif isinstance(obj, list):
        for v in obj:
            collect_rows(v, out)


def load_gsc(path):
    """-> {page key: {"clicks", "impr", "queries": {query: impressions}}}; clicks and impressions are the sums of the
    saved rows (page + query), so they leave out queries Search Console hides."""
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
            cq = next((lk[n] for n in ("query", "top queries") if n in lk), None)
            if not cu or "clicks" not in lk or "impressions" not in lk:
                sys.exit(f"{f}: needs url (or page), query, clicks and impressions columns. Columns: {list(df.columns)}")
            for _, r in df.iterrows():
                rows.append((r[cu], r[cq] if cq else None, float(r[lk['clicks']] or 0), float(r[lk['impressions']] or 0)))
        print(f"  GSC file {os.path.basename(f)}: {len(rows)} rows")
        if not rows:
            sys.exit(f"{f}: 0 rows read. Stop and show the person the response shape; do not guess a format.")
        if not any(q for _, q, _, _ in rows):
            sys.exit(f"{f}: the rows have no query. This review needs the page and query dimensions (references/composio-gsc.md).")
        for url, q, c, i in rows:
            d = total.setdefault(norm_url(url), {"clicks": 0, "impr": 0, "queries": {}})
            d["clicks"] += c
            d["impr"] += i
            if q:
                d["queries"][q.strip().lower()] = d["queries"].get(q.strip().lower(), 0) + i
    return total


# ------------------------------------------------------------------- keywords

def dedupe_key(term):
    k = re.sub(r"[\s\-]+", "", term.lower())
    return k[:-1] if len(k) > 3 and k.endswith("s") else k



def tokens(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.findall(r"[a-z0-9]+", s)

def term_key(term):
    """Same folding as dedupe_key, so 'med spa', 'medspa' and 'med-spa' (and a plural) are one term."""
    return dedupe_key("".join(tokens(term)))

def phrase_keys(text, maxn=6):
    """Every run of up to maxn consecutive words in the text, as term keys. A term is 'in' the text if its key is here."""
    t = tokens(text)
    return {dedupe_key("".join(t[i:j])) for i in range(len(t)) for j in range(i + 1, min(len(t), i + maxn) + 1)}


def term_tokens(s):
    """Words of a term with plurals folded, so 'injectables' and 'injectable' are the same word."""
    out = []
    for t in tokens(s):
        if t in STOP:
            continue
        if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        out.append(t)
    return out


def read_keywords(path, pages):
    """work/keywords.tsv: id <TAB> topic <TAB> keyword; keyword; ... (most important first)."""
    out, ids = {}, {p["id"] for p in pages}
    with open(path, encoding="utf-8-sig") as fh:
        for line in fh:
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            parts = [x.strip() for x in line.rstrip("\n").split("\t")]
            if not parts[0].isdigit():
                continue  # header row
            i = int(parts[0])
            if i not in ids:
                sys.exit(f"{path}: id {i} is not a page id in work/pages.tsv")
            topic = parts[1] if len(parts) > 1 else ""
            seen, kws = set(), []
            for k in re.split(r"[;|]", parts[2] if len(parts) > 2 else ""):
                k = k.strip()
                if k and dedupe_key(k) not in seen:
                    seen.add(dedupe_key(k))
                    kws.append(k)
            out[i] = (topic, kws[:MAX_KEYWORDS])
    missing = sorted(i for i in ids if not out.get(i, ("", []))[0])
    if missing:
        sys.exit(f"{path}: no topic for page ids {missing[:20]}{' ...' if len(missing) > 20 else ''}. Every page needs one.")
    return out


def read_recs(path, crawl_keys):
    """work/recommendations.tsv: recommended page <TAB> implied-by URL(s), ';' separated <TAB> reason."""
    rows = []
    if not path:
        return rows
    with open(path, encoding="utf-8-sig") as fh:
        for line in fh:
            parts = [x.strip() for x in line.rstrip("\n").split("\t")]
            if len(parts) < 3 or not parts[0] or parts[0].lower() == "recommended page":
                continue
            urls = [u.strip() for u in parts[1].split(";") if u.strip()]
            bad = [u for u in urls if norm_url(u) not in crawl_keys]
            if not urls or bad:
                sys.exit(f"{path}: '{parts[0]}' must name crawled URLs. Not in the crawl: {bad or 'none given'}")
            rows.append([parts[0], "\n".join(urls), parts[2]])
    return rows


def rank_keywords(kws, page_queries):
    """-> [(keyword, impressions or None)]. With Search Console data (page_queries is a dict), a keyword's
    impressions are the page's queries that contain all its words; ranked by impressions, ties and zeros keep the
    AI's order. Without it, the AI's order and no numbers."""
    if page_queries is None:
        return [(k, None) for k in kws[:5]]
    qt = [(set(term_tokens(q)), i) for q, i in page_queries.items()]
    scored = []
    for n, k in enumerate(kws):
        kt = set(term_tokens(k))
        imp = sum(i for t, i in qt if kt and kt <= t)
        scored.append((-imp, n, k, int(imp)))
    scored.sort()
    return [(k, imp) for _, _, k, imp in scored[:5]]


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

# ----------------------------------------------------------------------- main

def short(s, n=80):
    s = " ".join(s.split())
    return s if len(s) <= n else s[:n - 1] + "…"


def cmd_inspect(args):
    pages, cols, dups = load_crawl(args)
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "urls.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(p["url"] for p in pages) + "\n")
    with open(os.path.join(args.out, "pages.tsv"), "w", encoding="utf-8") as fh:
        fh.write("id\tpath\th1\ttitle\n")
        for i, p in enumerate(pages, 1):
            fh.write(f"{i}\t{p['path']}\t{short(p['h1'])}\t{short(p['title'].split('|')[0])}\n")
    print(f"Columns used: URL='{cols[0]}', H1='{cols[1]}', Title='{cols[2]}'")
    print(f"Pages: {len(pages)} (duplicate URLs skipped: {dups}); blank H1: {sum(not p['h1'] for p in pages)}; "
          f"blank title: {sum(not p['title'] for p in pages)}")
    print(f"Wrote {os.path.join(args.out, 'urls.txt')} and {os.path.join(args.out, 'pages.tsv')}")


def cmd_build(args):
    pages, cols, dups = load_crawl(args)
    for i, p in enumerate(pages, 1):
        p["id"] = i
    kw = read_keywords(args.keywords, pages)
    crawl_keys = {p["key"] for p in pages}
    recs = read_recs(args.recs, crawl_keys)
    gsc = load_gsc(args.gsc) if args.gsc else None
    cities = [c.strip() for c in (args.cities or "").split(",") if c.strip()]
    city_keys = {term_key(c) for c in cities}
    print(f"Pages: {len(pages)} (duplicates skipped {dups})")
    print("GSC: " + ("used" if gsc is not None else "not used (no --gsc): keywords in the AI's order, no numbers, export order"))
    print("City check: " + (", ".join(cities) if cities else "skipped (no --cities)"))

    for p in pages:
        p["topic"], kws = kw[p["id"]]
        p["notes"], p["flags"] = [], []
        g = gsc.get(p["key"]) if gsc is not None else None
        if gsc is not None:
            p["clicks"], p["impr"] = (int(g["clicks"]), int(g["impr"])) if g else (0, 0)
            if not g:
                p["notes"].append("No GSC data for this page; keywords are in the AI's order")
        p["lines"] = rank_keywords(kws, g["queries"] if g else None)
        if not p["lines"]:
            p["flags"].append(("nokeywords", "No target keywords. Choose them by hand"))
        if not p["h1"]:
            p["flags"].append(("blankh1", "Blank H1"))
        if not p["title"]:
            p["flags"].append(("blanktitle", "Blank Title Tag"))
        have = phrase_keys(p["title"]) | phrase_keys(p["h1"])
        if p["lines"] and not any(term_key(k) in have for k, _ in p["lines"]):
            p["flags"].append(("notrep", "None of the top keywords appear in the Title Tag or H1"))
        if city_keys and not (city_keys & have):
            p["flags"].append(("nocity", "No city in the Title Tag or H1"))

    if gsc is not None:
        matched = sum(1 for p in pages if p["key"] in gsc)
        rate = matched / len(pages) if pages else 0
        extra = sum(1 for k in gsc if k not in crawl_keys)
        print(f"GSC pages matched to crawled pages: {matched}/{len(pages)} ({rate:.0%}); GSC pages not in crawl: {extra}")
        if rate < 0.5:
            print("WARNING: under half the pages matched a GSC page. Check the property, the date range and the URL form "
                  "(http/https, www, trailing slash) before trusting the numbers.")

    gcols = ["GSC Clicks", "GSC Impressions"] if gsc is not None else []
    head = (["URL", "Review Needed", "Why Review", "Page Topic", "Current Page Title", "Current H1",
             "Suggested Page Title", "Suggested H1", "Update to Include"] + gcols + ["Notes"])
    width = {"URL": 45, "Review Needed": 11, "Why Review": 42, "Page Topic": 28, "Current Page Title": 40,
             "Current H1": 36, "Suggested Page Title": 40, "Suggested H1": 36, "Update to Include": 38,
             "GSC Clicks": 11, "GSC Impressions": 13, "Notes": 40}
    ordered = sorted(pages, key=lambda x: (-x["clicks"], -x["impr"], x["url"])) if gsc is not None else pages

    def line(k, v):
        return k if v is None else f"{k} - {v:,}"

    review = []
    for p in ordered:
        row = [p["url"], "Yes" if p["flags"] else "No", "\n".join(t for _, t in p["flags"]), p["topic"],
               p["title"], p["h1"], None, None, "\n".join(line(k, v) for k, v in p["lines"])]
        if gsc is not None:
            row += [p["clicks"], p["impr"]]
        row.append(" | ".join(p["notes"]))
        review.append(row)
    rec_rows = recs or [["None", "", "No obvious missing page."]]
    dhead = ["URL", "Page Path", "H1", "Title Tag"] + gcols
    data = [[p["url"], p["path"], p["h1"], p["title"]] + ([p["clicks"], p["impr"]] if gsc is not None else [])
            for p in pages]

    wb = Workbook()
    ws = add_sheet(wb, True, "Review", head, review, [width[h] for h in head],
                   numeric=("GSC Clicks", "GSC Impressions"), yellow=("Suggested Page Title", "Suggested H1"))
    note = ("Target keywords chosen from the page's path, H1 and title. Numbers are impressions of this page's Search "
            "Console queries that contain the keyword (not search volume); the page's clicks and impressions cover only "
            "the queries Search Console reports." if gsc is not None else
            "Target keywords chosen from the page's path, H1 and title, most important first. Not validated against "
            "search data: no Search Console access, so there are no numbers.")
    ws.cell(1, head.index("Update to Include") + 1).comment = Comment(note, "Mavan")
    for cell in ws[get_column_letter(2)][1:]:
        if cell.value == "Yes":
            cell.fill = PatternFill("solid", fgColor="F8CBAD")
    add_sheet(wb, False, "Recommendations", ["Recommended Page", "Implied By (URL)", "Reason"], rec_rows, [38, 55, 70])
    add_sheet(wb, False, "Data", dhead, data, [{"URL": 45, "Page Path": 36, "H1": 36, "Title Tag": 40, "GSC Clicks": 11,
                                                "GSC Impressions": 13}[h] for h in dhead],
              numeric=("GSC Clicks", "GSC Impressions"))
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    wb.save(args.out)
    print(f"Saved {args.out}")

    by_flag = defaultdict(int)
    for p in pages:
        for code, _ in p["flags"]:
            by_flag[code] += 1
    print(f"Review Needed = Yes on {sum(1 for p in pages if p['flags'])} of {len(pages)} pages; flags: {dict(by_flag)}")
    print(f"Recommendations: {len(recs)}")

    checks = [("Every crawled URL once in Data and once in Review",
               len(data) == len(review) == len(crawl_keys) and {norm_url(r[0]) for r in review} == crawl_keys),
              ("Update to Include: at most 5 keywords, no duplicates",
               all(len(p["lines"]) <= 5 and len({dedupe_key(k) for k, _ in p["lines"]}) == len(p["lines"]) for p in pages)),
              ("With Search Console data, keywords are ordered by impressions",
               all([v for _, v in p["lines"]] == sorted([v for _, v in p["lines"]], reverse=True)
                   for p in pages if p["lines"] and p["lines"][0][1] is not None)),
              ("Every page has a topic", all(p["topic"] for p in pages)),
              ("Every page with no keywords is marked Review Needed = Yes", all(p["flags"] for p in pages if not p["lines"]))]
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
            sp.add_argument("--keywords", required=True, help="work/keywords.tsv: the AI's topic and target keywords per page")
            sp.add_argument("--recs", help="work/recommendations.tsv: obvious missing pages. Optional")
            sp.add_argument("--gsc", help="folder (or file) of saved GSC page + query rows, .json or .csv. Optional: without it there are no numbers")
            sp.add_argument("--cities", help="the client's city or service-area cities, comma separated. Optional: without it the city check is skipped")
    args = ap.parse_args()
    cmd_inspect(args) if args.cmd == "inspect" else cmd_build(args)


if __name__ == "__main__":
    main()
