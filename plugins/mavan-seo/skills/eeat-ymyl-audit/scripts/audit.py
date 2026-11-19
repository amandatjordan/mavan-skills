#!/usr/bin/env python3
"""E-E-A-T & YMYL audit.

  python audit.py preflight --config config.json --crawl crawl.csv --outlinks outlinks.csv --out work [--external external.csv]
  python audit.py reps      --config config.json --crawl crawl.csv --outlinks outlinks.csv --external external.csv
  python audit.py queue     --config config.json --crawl crawl.csv --outlinks outlinks.csv --external external.csv --out work [--scope failed|all-high]
  python audit.py build     --config config.json --crawl crawl.csv --outlinks outlinks.csv --external external.csv
                            [--claims work/claims.tsv] [--chrome work/chrome.tsv] --out audit.xlsx

preflight: checks the config and the exports, prints what is ready, what is a warning and what stops the build, writes
           work/external_urls.txt (the deduped external destinations to crawl in list mode) and shows the start and end of the body
           text of one page per page type so the person can see whether the content selector is right.
reps:      proposes one typical page per page type (body word count closest to the type's median) for the Claude in Chrome check.
queue:     lists the pages for the accuracy review and writes each page's body text to work/text/ for the AI to read.
build:     builds the workbook. Every count, share and join happens here. Rules: references/rules.md.
The AI never types a number. It reads body text only for the accuracy review (queue) and writes claims.tsv / chrome.tsv.
"""
import argparse
import csv
import json
import os
import re
import statistics
import sys
import unicodedata
from collections import Counter, defaultdict
from urllib.parse import unquote, urlsplit

import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

URL_NAMES = ["address", "url", "page url"]
STATUS_NAMES = ["status code", "http status code", "status"]
INDEX_NAMES = ["indexability", "indexable status", "indexable"]
OL_SOURCE = ["source", "from", "source url", "source page"]
OL_DEST = ["destination", "to", "destination url", "link url", "target url", "link destination"]
OL_ANCHOR = ["anchor", "anchor text", "link text"]
OL_POS = ["link position", "position"]
OL_TYPE = ["type", "link type"]
OL_STATUS = ["status code", "http status code"]
EXT_STATUS = STATUS_NAMES
EXT_TITLE = ["title 1", "title", "page title"]
EXT_H1 = ["h1-1", "h1", "h1 1"]

TIERS = ["High", "Medium", "Low"]
BLOCKED = {401, 403, 429, 999}
STOP_WORDS = set("a an and or the of in on for to with by at as is are be from vs near me your you our we it its this that these those into".split())
GENERIC_WORDS = set("click here read more link article source sources page website site learn see visit via official research study studies shows show shown according report info information".split())
FLAGGED = ["Dead link", "No response", "Redirect", "Goes to homepage", "No shared words", "Weak source"]
ACTIONS = {
    "No author shown": "Show a named author on the page, linked to a bio page.",
    "No medical / expert reviewer": "Add a reviewer line with the reviewer's credentials and the review date.",
    "No credentials found": "Show the author's or reviewer's credentials on the page or on the bio page it links to.",
    "No published date": "Show the published date and the date the page was last reviewed.",
    "No external citations": "Cite primary sources (government, academic, professional bodies) for the claims on the page.",
    "Flagged external links": "Fix each flagged link on the External Links tab: replace dead links, update redirects, and point links at the page that supports the claim.",
    "No schema": "Add the schema type that fits the page type.",
}
CHECKS = list(ACTIONS)
NO_VALUES = {"", "0", "false", "no", "none", "nan"}


# ------------------------------------------------------------------ helpers
def read_table(path):
    if path.lower().endswith((".xlsx", ".xlsm")):
        df = pd.read_excel(path, dtype=str).fillna("")
    else:
        df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig", encoding_errors="replace")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def find_col(df, names):
    lookup = {c.lower(): c for c in df.columns}
    for n in names:
        if n in lookup:
            return lookup[n]
    return None


def host_of(u):
    u = str(u).strip()
    if not re.match(r"^[a-z][a-z0-9+.-]*://", u, re.I):
        u = "//" + u
    h = urlsplit(u).netloc.lower().split("@")[-1].split(":")[0]
    return h[4:] if h.startswith("www.") else h


def norm_url(u):
    u = str(u).strip()
    if not re.match(r"^[a-z][a-z0-9+.-]*://", u, re.I):
        u = "//" + u
    p = urlsplit(u)
    path = unquote(p.path or "/")
    if len(path) > 1:
        path = path.rstrip("/")
    return (host_of(u) + path + ("?" + p.query if p.query else "")).lower()


def path_of(u):
    return (unquote(urlsplit(str(u).strip()).path) or "/").lower()


def words(text):
    return re.findall(r"[a-z0-9]+", unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode().lower())


def stem(w):
    return w[:-1] if len(w) > 3 and w.endswith("s") else w


def to_int(v):
    try:
        return int(float(str(v).strip()))
    except ValueError:
        return 0


def present(v):
    return str(v).strip().lower() not in NO_VALUES


def clean_text(v):
    return re.sub(r"\s+", " ", str(v)).strip()


# ------------------------------------------------------------------ config
def load_config(path, findings):
    try:
        with open(path, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except (OSError, ValueError) as e:
        sys.exit(f"STOP: cannot read config {path}: {e}")
    cfg.setdefault("columns", {})
    cfg.setdefault("priority_cutoffs", {"high": 4, "medium": 2})
    cfg.setdefault("content_link_positions", ["Content"])
    for k in ("weak_domains", "generic_anchor_words", "experience_terms", "own_domains", "credential_terms"):
        cfg.setdefault(k, [])
    cfg.setdefault("authoritative", {})
    cfg["authoritative"].setdefault("tlds", [])
    cfg["authoritative"].setdefault("domains", [])
    if not cfg["columns"].get("body"):
        findings.append(("STOP", "Config has no columns.body: the crawl column that holds each page's body text."))
    rules = cfg.get("page_types") or []
    if not rules:
        findings.append(("STOP", "Config has no page_types: which URL paths are conditions, services, blogs and so on."))
    for r in rules:
        if not r.get("name") or not r.get("paths") or r.get("tier") not in TIERS:
            findings.append(("STOP", f"Page type {r.get('name', '?')} needs a name, paths and a tier of High, Medium or Low."))
    if not cfg["credential_terms"]:
        findings.append(("STOP", "Config has no credential_terms (for example MD, DDS, board-certified)."))
    if not (cfg["authoritative"]["tlds"] or cfg["authoritative"]["domains"]):
        findings.append(("STOP", "Config has no authoritative rules (tlds or domains)."))
    return cfg


def is_blank(name):
    return not name or str(name).strip().lower() in {"", "none", "n/a", "not present"}


def resolve(df, name, label, findings):
    """Return the real column for a config column name; None when the site does not have it."""
    if is_blank(name):
        return None
    lookup = {c.lower(): c for c in df.columns}
    if str(name).strip().lower() in lookup:
        return lookup[str(name).strip().lower()]
    findings.append(("STOP", f"Config names the {label} column '{name}' but the crawl export has no such column. Columns: {list(df.columns)}"))
    return None


def page_type(path, rules):
    for r in rules:
        if any(p.lower() in path for p in r["paths"]):
            return r["name"], r["tier"]
    return None, None


def domain_type(host, cfg):
    a = cfg["authoritative"]
    for t in a["tlds"]:
        if host.endswith(t.lower().lstrip("*")):
            return "Authoritative"
    for d in a["domains"]:
        d = d.lower().lstrip(".")
        if host == d or host.endswith("." + d):
            return "Authoritative"
    for d in cfg["weak_domains"]:
        d = d.lower().lstrip(".")
        if host == d or host.endswith("." + d):
            return "Weak source"
    return "Other"


def term_hits(text, terms):
    found = []
    for t in terms:
        t = t.strip()
        if not t:
            continue
        flags = 0 if (t.isupper() and len(t) <= 5) else re.I
        if re.search(r"(?<![A-Za-z0-9])" + re.escape(t) + r"(?![A-Za-z0-9])", text, flags):
            found.append(t)
    return found


def experience_hits(text, cfg):
    out = [m.group(0) for m in re.finditer(r"\b\d{1,2}\+?\s*(?:years?|yrs?)\b(?:\s+of)?\s*(?:clinical\s+)?(?:experience|practice)", text, re.I)]
    out += term_hits(text, cfg["experience_terms"])
    return out[:3]


def anchor_match(anchor, dest_text, cfg):
    """Match / Partial / No match / Generic anchor / Not checked. Plain word overlap, no judgement."""
    skip = STOP_WORDS | GENERIC_WORDS | {w.lower() for w in cfg["generic_anchor_words"]}
    aw = {stem(w) for w in words(anchor) if w not in skip}
    if not aw:
        return "Generic anchor"
    dw = {stem(w) for w in words(dest_text)}
    if not dw:
        return "Not checked"
    hit = len(aw & dw)
    return "Match" if hit == len(aw) else ("Partial" if hit else "No match")


# ------------------------------------------------------------------ analysis
def analyze(args, need_external):
    findings = []
    cfg = load_config(args.config, findings)
    try:
        crawl = read_table(args.crawl)
        outl = read_table(args.outlinks)
    except Exception as e:  # unreadable export
        sys.exit(f"STOP: cannot read an export: {e}")
    ext = None
    if getattr(args, "external", None):
        try:
            ext = read_table(args.external)
        except Exception as e:
            sys.exit(f"STOP: cannot read the external list crawl export: {e}")
    elif need_external:
        findings.append(("STOP", "The list crawl export of the external destinations is missing (--external)."))

    c = cfg["columns"]
    ucol = resolve(crawl, c.get("url"), "url", findings) if c.get("url") else find_col(crawl, URL_NAMES)
    if not ucol:
        findings.append(("STOP", f"Crawl export has no URL column. Columns: {list(crawl.columns)}. Name it in config columns.url."))
    scol = resolve(crawl, c.get("status"), "status", findings) if c.get("status") else find_col(crawl, STATUS_NAMES)
    icol = resolve(crawl, c.get("indexability"), "indexability", findings) if c.get("indexability") else find_col(crawl, INDEX_NAMES)
    cols = {k: resolve(crawl, c.get(k), k, findings) for k in
            ("body", "author", "reviewer", "published", "updated", "schema", "testimonials", "before_after", "rating")}

    osrc, odst = find_col(outl, OL_SOURCE), find_col(outl, OL_DEST)
    oanc, opos, otype, ostat = (find_col(outl, n) for n in (OL_ANCHOR, OL_POS, OL_TYPE, OL_STATUS))
    if not (osrc and odst):
        findings.append(("STOP", f"Outlinks export needs a source and a destination column. Columns: {list(outl.columns)}"))
    if not oanc:
        findings.append(("STOP", f"Outlinks export has no anchor text column. Columns: {list(outl.columns)}"))
    if any(l == "STOP" for l, _ in findings):
        return dict(findings=findings, cfg=cfg)

    # ---- pages
    own_hosts = {host_of(u) for u in crawl[ucol] if u} | {h.lower().lstrip(".") for h in cfg["own_domains"]}
    pages, order = {}, []
    excluded = Counter()
    unmatched = []
    for _, r in crawl.iterrows():
        url = r[ucol].strip()
        if not url:
            continue
        status = to_int(r[scol]) if scol else 200
        if scol and status != 200:
            excluded["did not return 200"] += 1
            continue
        if icol and not str(r[icol]).strip().lower().startswith("indexable"):
            excluded["not indexable"] += 1
            continue
        ptype, tier = page_type(path_of(url), cfg["page_types"])
        if not ptype:
            unmatched.append(url)
            continue
        val = lambda k: clean_text(r[cols[k]]) if cols[k] else None
        body = val("body") or ""
        author, reviewer = val("author"), val("reviewer")
        cred_text = " ".join([body, author or "", reviewer or ""])
        p = dict(url=url, key=norm_url(url), ptype=ptype, tier=tier, body=body, words=len(body.split()),
                 author=author, reviewer=reviewer, published=val("published"), updated=val("updated"), schema=val("schema"),
                 testimonials=val("testimonials"), before_after=val("before_after"), rating=val("rating"),
                 creds=term_hits(cred_text, cfg["credential_terms"]), exp=experience_hits(body, cfg), links=[])
        pages[p["key"]] = p
        order.append(p["key"])

    # ---- links
    positions = {x.lower() for x in cfg["content_link_positions"]}
    ext_map = {}
    if ext is not None:
        eu = find_col(ext, URL_NAMES)
        if not eu:
            findings.append(("STOP", f"External list crawl export has no URL column. Columns: {list(ext.columns)}"))
            return dict(findings=findings, cfg=cfg)
        es, et, eh = find_col(ext, EXT_STATUS), find_col(ext, EXT_TITLE), find_col(ext, EXT_H1)
        for _, r in ext.iterrows():
            ext_map[norm_url(r[eu])] = dict(status=to_int(r[es]) if es else 0, title=clean_text(r[et]) if et else "", h1=clean_text(r[eh]) if eh else "")
    seen, links, dest_urls = set(), [], {}
    skipped_position = 0
    for _, r in outl.iterrows():
        if otype and str(r[otype]).strip().lower() not in {"hyperlink", "link", "a", "anchor"}:
            continue
        src, dst = norm_url(r[osrc]), str(r[odst]).strip()
        if src not in pages or not re.match(r"^https?://", dst, re.I) or host_of(dst) in own_hosts:
            continue
        if opos and str(r[opos]).strip().lower() not in positions:
            skipped_position += 1
            continue
        dkey = norm_url(dst)
        if (src, dkey) in seen:
            continue
        seen.add((src, dkey))
        dest_urls.setdefault(dkey, dst)
        e = ext_map.get(dkey)
        status = e["status"] if e and e["status"] else (to_int(r[ostat]) if ostat else 0)
        title, h1 = (e["title"], e["h1"]) if e else ("", "")
        host = host_of(dst)
        dtype = domain_type(host, cfg)
        match = anchor_match(r[oanc], title + " " + h1, cfg) if e else "Not checked"
        flags = []
        if status >= 400 and status not in BLOCKED:
            flags.append("Dead link")
        elif status == 0:
            flags.append("No response")
        elif 300 <= status < 400:
            flags.append("Redirect")
        if path_of(dst) in ("/", "") and not urlsplit(dst).query:
            flags.append("Goes to homepage")
        if match == "No match":
            flags.append("No shared words")
        if dtype == "Weak source":
            flags.append("Weak source")
        if status in BLOCKED:
            flags.append("Check manually")
        row = dict(src=pages[src]["url"], pkey=src, anchor=clean_text(r[oanc]), dest=dst, status=status, title=title, h1=h1,
                   dtype=dtype, host=host, match=match, flags=flags, flagged=[f for f in flags if f in FLAGGED])
        pages[src]["links"].append(row)
        links.append(row)

    # ---- checks per page
    cut = cfg["priority_cutoffs"]
    for k in order:
        p = pages[k]
        p["cites"] = len(p["links"])
        p["auth"] = sum(1 for l in p["links"] if l["dtype"] == "Authoritative")
        p["flagged_n"] = sum(1 for l in p["links"] if l["flagged"])
        fails = []
        if p["author"] is not None and not present(p["author"]):
            fails.append("No author shown")
        if p["reviewer"] is not None and not present(p["reviewer"]):
            fails.append("No medical / expert reviewer")
        if not p["creds"]:
            fails.append("No credentials found")
        if p["published"] is not None and not present(p["published"]):
            fails.append("No published date")
        if p["cites"] == 0:
            fails.append("No external citations")
        if p["flagged_n"]:
            fails.append("Flagged external links")
        if p["schema"] is not None and not present(p["schema"]):
            fails.append("No schema")
        p["fails"] = fails
        if p["tier"] == "Low":
            p["priority"] = "Not scored"
        else:
            n = len(fails)
            p["priority"] = "High" if n >= cut["high"] else ("Medium" if n >= cut["medium"] else "Low")

    # ---- findings
    n_pages = len(order)
    if not n_pages:
        findings.append(("STOP", "No crawled page matches any page type pattern in the config."))
    elif all(not pages[k]["body"] for k in order):
        findings.append(("STOP", "Body text is empty on every page: the content selector is wrong, or the site needs JavaScript rendering."))
    if not dest_urls and not any(l == "STOP" for l, _ in findings):
        findings.append(("STOP", "The outlinks export has no external links from these pages: external link crawling was off, or the link position setting excludes them all."))
    if ext is None and not need_external:
        findings.append(("WARN", "The list crawl of the external destinations is not done yet: crawl work/external_urls.txt in list mode, then re-run preflight with --external."))
    if n_pages:
        def some_empty(label, key, keys):
            empty = [pages[k]["url"] for k in keys if pages[k][key] is not None and not present(pages[k][key])]
            if empty:
                findings.append(("WARN", f"{label} is empty on {len(empty)} of {len(keys)} pages (first: {', '.join(empty[:3])}). If the pages do show it, the selector is wrong."))
        some_empty("Body text", "body", order)
        scored_keys = [k for k in order if pages[k]["tier"] != "Low"]  # Low-YMYL pages are not scored, so a blank author there is expected
        for lab, key in (("Author", "author"), ("Reviewer", "reviewer"), ("Published date", "published")):
            some_empty(lab, key, scored_keys)
        for lab, key in (("testimonial", "testimonials"), ("before/after photo", "before_after"), ("rating", "rating")):
            if cols[key] and not any(present(pages[k][key]) for k in order):
                findings.append(("WARN", f"No page has a {lab} marker hit. If the site shows them, the marker is wrong."))
        if not opos:
            findings.append(("WARN", "The outlinks export has no link position column: links in the menu and footer are counted as citations."))
        elif skipped_position:
            findings.append(("OK", f"{skipped_position} external links outside the content area (menu, footer) were left out."))
    if unmatched:
        findings.append(("WARN", f"{len(unmatched)} crawled page(s) match no page type and are left out (first: {', '.join(unmatched[:3])})."))
    for why, n in excluded.items():
        findings.append(("WARN", f"{n} crawled page(s) left out: {why}."))
    if ext is not None:
        missing = [u for k, u in dest_urls.items() if k not in ext_map]
        if missing:
            findings.append(("WARN", f"{len(missing)} external destinations are not in the list crawl (shown as Not checked; first: {', '.join(missing[:3])})."))
        manual = sorted({l["dest"] for l in links if l["status"] in BLOCKED})
        if manual:
            findings.append(("WARN", f"{len(manual)} external destinations blocked the crawler (401, 403, 429 or 999) and need a manual check."))
    return dict(findings=findings, cfg=cfg, pages=pages, order=order, links=links, dest_urls=dest_urls)


def print_findings(findings):
    for lvl, msg in findings:
        print(f"{'READY' if lvl == 'OK' else lvl}: {msg}")


def stop_if_needed(res):
    if any(l == "STOP" for l, _ in res["findings"]):
        print_findings(res["findings"])
        sys.exit("STOP: fix the items above before building.")


# ------------------------------------------------------------------ commands
def cmd_preflight(args):
    res = analyze(args, need_external=False)
    os.makedirs(args.out, exist_ok=True)
    stops = [m for l, m in res["findings"] if l == "STOP"]
    if "pages" in res and not stops:
        with open(os.path.join(args.out, "external_urls.txt"), "w", encoding="utf-8") as fh:
            fh.write("\n".join(res["dest_urls"].values()) + "\n")
        print(f"READY: {len(res['order'])} pages matched {len({res['pages'][k]['ptype'] for k in res['order']})} page types; "
              f"{len(res['links'])} external links to {len(res['dest_urls'])} destinations. Destinations written to {args.out}/external_urls.txt")
        seen = set()
        print("\nSample body text, one page per page type (check it is the article text, not the menu or footer):")
        for k in res["order"]:
            p = res["pages"][k]
            if p["ptype"] in seen:
                continue
            seen.add(p["ptype"])
            w = p["body"].split()
            print(f"\n[{p['ptype']}] {p['url']} ({len(w)} words)\n  START: {' '.join(w[:40])}\n  END:   {' '.join(w[-40:])}")
        print()
    print_findings(res["findings"])
    if stops:
        sys.exit(1)


def cmd_reps(args):
    res = analyze(args, need_external=True)
    stop_if_needed(res)
    by = defaultdict(list)
    for k in res["order"]:
        by[res["pages"][k]["ptype"]].append(res["pages"][k])
    for name, ps in by.items():
        med = statistics.median(p["words"] for p in ps)
        rep = min(ps, key=lambda p: abs(p["words"] - med))
        print(f"{name}\t{rep['url']}\t{rep['words']} words (median {med:g}, {len(ps)} pages)")


def scoped(res, scope):
    out = []
    for k in res["order"]:
        p = res["pages"][k]
        if p["tier"] == "High" and (scope == "all-high" or p["fails"]):
            out.append(p)
    return sorted(out, key=lambda p: -len(p["fails"]))


def why(p):
    parts = list(p["fails"]) or ["High-YMYL page (no structural check failed)"]
    return "; ".join(parts)


def cmd_queue(args):
    res = analyze(args, need_external=True)
    stop_if_needed(res)
    for sc in ("failed", "all-high"):
        q = scoped(res, sc)
        print(f"scope {sc}: {len(q)} pages, {sum(p['words'] for p in q)} words of body text")
    q = scoped(res, args.scope)
    tdir = os.path.join(args.out, "text")
    os.makedirs(tdir, exist_ok=True)
    with open(os.path.join(args.out, "queue.tsv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["id", "url", "page_type", "words", "external_citations", "why_in_queue"])
        for i, p in enumerate(q, 1):
            w.writerow([i, p["url"], p["ptype"], p["words"], p["cites"], why(p)])
            with open(os.path.join(tdir, f"{i:03d}.txt"), "w", encoding="utf-8") as t:
                t.write(f"URL: {p['url']}\nExternal citations on the page: {p['cites']}\n\n{p['body']}\n")
    print(f"Queue ({args.scope}) written to {args.out}/queue.tsv and {args.out}/text/")


# ------------------------------------------------------------------ workbook
FONT = "Arial"
HDR_FILL = PatternFill("solid", start_color="1F3864")
YELLOW = PatternFill("solid", start_color="FFF2CC")
FILLS = {"High": PatternFill("solid", start_color="F8CBAD"), "Medium": PatternFill("solid", start_color="FFE699"),
         "Low": PatternFill("solid", start_color="C6E0B4")}
RED = PatternFill("solid", start_color="F8CBAD")


def write_sheet(wb, title, header, rows, widths, yellow=(), name=None, fills=None):
    ws = wb.create_sheet(title)
    ws.append(header)
    for r in rows:
        ws.append(r)
    for c in ws[1]:
        c.font, c.fill = Font(name=FONT, bold=True, color="FFFFFF", size=10), HDR_FILL
        c.alignment = Alignment(wrap_text=True, vertical="center")
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.font = Font(name=FONT, size=10)
            c.alignment = Alignment(wrap_text=True, vertical="top")
            if c.column in yellow:
                c.fill = YELLOW
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"
    if fills:
        for col, mapping in fills.items():
            for row in ws.iter_rows(min_row=2, min_col=col, max_col=col):
                for c in row:
                    if c.value in mapping:
                        c.fill = mapping[c.value]
    if rows:
        t = Table(displayName=name or re.sub(r"\W", "", title), ref=f"A1:{get_column_letter(len(header))}{len(rows) + 1}")
        t.tableStyleInfo = TableStyleInfo(name="TableStyleLight1", showRowStripes=False)
        ws.add_table(t)
    return ws


def na(v):
    return "n/a" if v is None else v


def yn(v):
    return "n/a" if v is None else ("Yes" if present(v) else "No")


def read_tsv(path, need):
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    for col in need:
        if not rows or col not in rows[0]:
            sys.exit(f"STOP: {path} needs the columns {need}.")
    return rows


def cmd_build(args):
    res = analyze(args, need_external=True)
    stop_if_needed(res)
    cfg, pages, order, links = res["cfg"], res["pages"], res["order"], res["links"]
    scored = [pages[k] for k in order if pages[k]["tier"] != "Low"]
    queue = scoped(res, args.scope)

    claims = {}
    if args.claims:
        for r in read_tsv(args.claims, ["url", "specific_claims", "claims_to_verify"]):
            claims[norm_url(r["url"])] = r
        unknown = [u for u in claims if u not in pages]
        if unknown:
            sys.exit(f"STOP: claims.tsv has URLs that are not audited pages: {unknown[:3]}")
        bad = [r["url"] for r in claims.values() if r["specific_claims"] not in ("Yes", "No")]
        if bad:
            sys.exit(f"STOP: claims.tsv specific_claims must be Yes or No: {bad[:3]}")
    chrome = []
    if args.chrome:
        chrome = read_tsv(args.chrome, ["url", "visitor_sees", "agrees", "opportunities"])
        for r in chrome:
            if norm_url(r["url"]) not in pages:
                sys.exit(f"STOP: chrome.tsv has a URL that is not an audited page: {r['url']}")

    wb = Workbook()
    wb.remove(wb.active)

    # ---- Recommendations
    ws = wb.create_sheet("Recommendations")
    f10, b10 = Font(name=FONT, size=10), Font(name=FONT, size=10, bold=True)
    r = 1
    ws.cell(r, 1, "E-E-A-T & YMYL audit").font = Font(name=FONT, size=14, bold=True)
    r += 2
    warns = [m for l, m in res["findings"] if l == "WARN"]
    ws.cell(r, 1, "Preflight warnings").font = b10
    for m in warns or ["None"]:
        r += 1
        ws.cell(r, 1, m).font = f10
    r += 2
    for lab, val in (("Pages audited", len(order)), ("Pages scored (Medium and High YMYL)", len(scored)),
                     ("External links checked", len(links)),
                     ("Pages in the accuracy review queue", len(queue))):
        ws.cell(r, 1, lab).font = b10
        ws.cell(r, 2, val).font = f10
        ws.cell(r, 2).alignment = Alignment(horizontal="left")
        r += 1
    r += 1

    def table(title, header, rows, widths=None):
        nonlocal r
        ws.cell(r, 1, title).font = b10
        r += 1
        for i, h in enumerate(header, 1):
            c = ws.cell(r, i, h)
            c.font, c.fill = Font(name=FONT, bold=True, color="FFFFFF", size=10), HDR_FILL
            c.alignment = Alignment(wrap_text=True)
        for row in rows:
            r += 1
            for i, v in enumerate(row, 1):
                c = ws.cell(r, i, v)
                c.font, c.alignment = f10, Alignment(wrap_text=True, vertical="top", horizontal="left")
        r += 2

    issue_rows = []
    for chk in CHECKS:
        hit = [p for p in scored if chk in p["fails"]]
        if hit:
            ex = ", ".join(p["url"] for p in sorted(hit, key=lambda p: -len(p["fails"]))[:3])
            pct = len(hit) / len(scored) if scored else 0
            issue_rows.append((chk, len(hit), f"{pct:.0%}", ex, ACTIONS[chk]))
    if claims:
        hit = [p for k, p in pages.items() if k in claims and claims[k]["specific_claims"] == "Yes" and p["cites"] == 0]
        if hit:
            issue_rows.append(("Makes specific claims and has no external citations", len(hit), "", ", ".join(p["url"] for p in hit[:3]),
                               "Cite a primary source for each specific claim or remove the claim."))
    issue_rows.sort(key=lambda x: -x[1])
    table("Issues, most common first (scored pages)", ["Issue", "Pages affected", "% of scored pages", "Example pages", "Recommended action"],
          issue_rows or [("No issue found", 0, "0%", "", "")])
    tt = []
    for rule in cfg["page_types"]:
        ps = [pages[k] for k in order if pages[k]["ptype"] == rule["name"]]
        if ps:
            tt.append((rule["name"], rule["tier"], len(ps)) + tuple(sum(1 for p in ps if p["priority"] == x) for x in ("High", "Medium", "Low")))
    table("By page type", ["Page type", "YMYL tier", "Pages", "High priority", "Medium priority", "Low priority"], tt)
    all_p = [pages[k] for k in order]
    cov = []
    for lab, fn in (("Customer reviews / testimonials", lambda p: p["testimonials"]), ("Before/after or results photos", lambda p: p["before_after"]),
                    ("Rating shown on the page", lambda p: p["rating"])):
        if any(fn(p) is not None for p in all_p):
            n = sum(1 for p in all_p if fn(p) is not None and present(fn(p)))
            cov.append((lab, n, f"{n / len(all_p):.0%}"))
    n = sum(1 for p in all_p if p["creds"])
    cov.append(("Credentials found", n, f"{n / len(all_p):.0%}"))
    n = sum(1 for p in all_p if p["exp"])
    cov.append(("Years of experience stated", n, f"{n / len(all_p):.0%}"))
    table("Trust signals present (all audited pages)", ["Signal", "Pages with it", "% of audited pages"], cov)
    fl = Counter(f for l in links for f in l["flags"])
    table("External links by flag", ["Flag", "Links"], [(f, fl[f]) for f in FLAGGED + ["Check manually"] if fl[f]] or [("No flags", 0)])
    for i, w in enumerate((46, 18, 18, 70, 70), 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # ---- Page Review
    head = ["URL", "Page type", "YMYL tier", "Author shown", "Reviewer shown", "Credentials found", "Years of experience", "Published",
            "Last updated", "Schema types", "External citations", "Authoritative citations", "Authoritative share", "Flagged external links",
            "Testimonials or reviews", "Before/after photos", "Rating shown on page", "Specific claims found", "Checks failed", "Priority",
            "Failed checks"]
    rows = []
    for k in order:
        p = pages[k]
        share = f"{p['auth'] / p['cites']:.0%}" if p["cites"] else "No citations"
        sc = claims[k]["specific_claims"] if k in claims else ("Not read" if p["tier"] == "High" else "n/a")
        rows.append([p["url"], p["ptype"], p["tier"], yn(p["author"]), yn(p["reviewer"]), ", ".join(p["creds"]) or "None",
                     ", ".join(p["exp"]) or "None", na(p["published"]) if p["published"] is None else (p["published"] or "None"),
                     na(p["updated"]) if p["updated"] is None else (p["updated"] or "None"),
                     na(p["schema"]) if p["schema"] is None else (p["schema"] or "None"), p["cites"], p["auth"], share, p["flagged_n"],
                     yn(p["testimonials"]) if p["testimonials"] is not None else "Not set up",
                     yn(p["before_after"]) if p["before_after"] is not None else "Not set up",
                     (p["rating"] if present(p["rating"]) else "No") if p["rating"] is not None else "Not set up", sc,
                     len(p["fails"]) if p["tier"] != "Low" else "Not scored", p["priority"],
                     "; ".join(p["fails"]) if p["tier"] != "Low" else ""])
    write_sheet(wb, "Page Review", head, rows, [44, 14, 10, 10, 10, 22, 14, 12, 12, 22, 10, 12, 12, 10, 12, 12, 14, 12, 9, 11, 50],
                name="PageReview", fills={20: FILLS})

    # ---- External Links
    head = ["Source page", "Anchor text", "Destination URL", "Destination status", "Destination title", "Destination H1", "Domain type",
            "Anchor vs destination", "Flag", "Reviewer note"]
    rows = [[l["src"], l["anchor"], l["dest"], l["status"] or "No response", l["title"], l["h1"], l["dtype"], l["match"], "; ".join(l["flags"]), None]
            for l in links]
    write_sheet(wb, "External Links", head, rows, [40, 28, 46, 12, 34, 28, 14, 14, 28, 30], yellow=(10,), name="ExternalLinks")

    # ---- Accuracy Review Queue
    head = ["URL", "Page type", "Why it is in the queue", "External citations", "Specific claims found", "Claims to verify",
            "Cited sources", "Reviewer", "Result", "Notes"]
    rows = []
    for p in queue:
        cl = claims.get(p["key"])
        rows.append([p["url"], p["ptype"], why(p), p["cites"], cl["specific_claims"] if cl else "Not read",
                     cl["claims_to_verify"] if cl else "", "\n".join(l["dest"] for l in p["links"]), None, None, None])
    write_sheet(wb, "Accuracy Review Queue", head, rows, [44, 14, 44, 10, 12, 60, 50, 14, 16, 30], yellow=(8, 9, 10), name="AccuracyQueue")

    # ---- Chrome Page Check (only when the person ran it)
    if chrome:
        head = ["Page type", "URL", "What the crawl detected", "What a visitor sees", "Agrees with the crawl", "Other opportunities"]
        rows = []
        for cr in chrome:
            p = pages[norm_url(cr["url"])]
            seen = (f"Author: {yn(p['author'])}; reviewer: {yn(p['reviewer'])}; credentials: {', '.join(p['creds']) or 'None'}; "
                    f"testimonials: {yn(p['testimonials'])}; before/after: {yn(p['before_after'])}; rating: "
                    f"{(p['rating'] if present(p['rating']) else 'No') if p['rating'] is not None else 'Not set up'}")
            rows.append([p["ptype"], p["url"], seen, cr["visitor_sees"], cr["agrees"], cr["opportunities"]])
        write_sheet(wb, "Chrome Page Check", head, rows, [14, 44, 50, 60, 14, 60], name="ChromePageCheck")

    out = args.out
    wb.save(out)
    qa(out, pages, order, links, queue, scored, args)
    print(f"Saved {out}")


def qa(path, pages, order, links, queue, scored, args):
    wb = load_workbook(path)
    ok = True

    def check(label, cond):
        nonlocal ok
        print(f"{'PASS' if cond else 'FAIL'}: {label}")
        ok = ok and cond

    pr = list(wb["Page Review"].iter_rows(min_row=2, values_only=True))
    check("every audited page appears once in Page Review", [r[0] for r in pr] == [pages[k]["url"] for k in order] and len({r[0] for r in pr}) == len(pr))
    el = list(wb["External Links"].iter_rows(min_row=2, values_only=True))
    check("External Links has one row per source page and destination", len(el) == len(links) == len({(l["pkey"], norm_url(l["dest"])) for l in links}))
    check("page citation counts add up to the External Links rows", sum(r[10] for r in pr) == len(el))
    check("Low-YMYL pages are not scored", all(r[18] == "Not scored" and r[19] == "Not scored" for r in pr if r[2] == "Low"))
    check("every scored page has a priority", all(r[19] in ("High", "Medium", "Low") for r in pr if r[2] != "Low"))
    aq = list(wb["Accuracy Review Queue"].iter_rows(min_row=2, values_only=True))
    check("every queued page is a High-YMYL audited page", all(pages[norm_url(r[0])]["tier"] == "High" for r in aq))
    check("flagged counts match the External Links flags", sum(r[13] for r in pr) == sum(1 for r in el if any(f in (r[8] or "") for f in FLAGGED)))
    if not ok:
        sys.exit("QA failed")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("preflight", "reps", "queue", "build"):
        s = sub.add_parser(name)
        s.add_argument("--config", required=True)
        s.add_argument("--crawl", required=True)
        s.add_argument("--outlinks", required=True)
        s.add_argument("--external")
        if name in ("preflight", "queue", "build"):
            s.add_argument("--out", required=True)
        if name in ("queue", "build"):
            s.add_argument("--scope", choices=["failed", "all-high"], default="failed")
        if name == "build":
            s.add_argument("--claims")
            s.add_argument("--chrome")
    args = ap.parse_args()
    {"preflight": cmd_preflight, "reps": cmd_reps, "queue": cmd_queue, "build": cmd_build}[args.cmd](args)


if __name__ == "__main__":
    main()
