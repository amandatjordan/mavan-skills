#!/usr/bin/env python3
"""Service Page H1 & Title Tag Review.

  python build.py inspect    --crawl export.csv --out work
  python build.py candidates --crawl export.csv --topics work/topics.tsv --out work
  python build.py build      --crawl export.csv --topics work/topics.tsv [--strikes work/strikes.tsv]
                             --out review.xlsx [--gsc work/gsc] [--cities "City, City"]

inspect:    shows which export columns are used, writes work/urls.txt (for the GSC filter) and work/pages.tsv
            (one compact line per page, with the taxonomy's guess, for the AI to read).
candidates: from the AI's page topics, lists the keywords in the keyword list that fit each page (work/candidates.txt).
build:      applies the AI's topics and strikes, picks the top 5 by volume, flags the pages a person should review,
            builds the three-tab workbook, writes the missing-keywords list and runs the QA checks.
            --gsc is optional: without it the workbook has no clicks or impressions and keeps the export order.
            --cities is optional: without it the city check is skipped.
The AI decides what each page is about and which candidate keywords fit it. Every number, count and join happens
here; the AI never types a volume. Rules: references/rules.md.
"""
import argparse
import csv
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
                    return None, field, (f"Could not pick one taxonomy entry: {len(top)} {lvl} entries match "
                                         f"({names}). Choose the right one and its keywords by hand")
    return None, "", "Could not match this page to the taxonomy. Choose its service and keywords by hand"


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


def ranked(items):
    """Group by Base Term (see dedupe_key), keep the highest volume of each group, highest first."""
    best = {}
    for kwd, base, vol in items:
        term = (base or kwd).strip()
        k = dedupe_key(term)
        cand = (-vol, len(term), term)
        if k not in best or cand < best[k]:
            best[k] = cand
    return [(t, -v) for v, _, t in sorted(best.values())]


def top5(items):
    return ranked(items)[:5]


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


STOP = {"and", "or", "in", "for", "of", "the", "a", "an", "to", "with", "near", "me", "by", "vs"}
MAX_TOPIC, MAX_BORROW, FEW = 12, 3, 3  # candidates per page from the topic / from entries with no page; "few" = under FEW


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


def load_keyword_rows(path):
    """Every All Keywords row except Class = Exclude: (keyword, base term, volume, set of words in the base term)."""
    kw = pd.read_excel(path, sheet_name="All Keywords", dtype=str).fillna("")
    kw.columns = [c.strip() for c in kw.columns]
    base = next(c for c in kw.columns if c.startswith("Base Term"))
    vols = pd.to_numeric(kw["Volume"].str.replace(",", ""), errors="coerce").fillna(0).astype(int)
    rows = []
    for k, b, v, c in zip(kw["Keyword"], kw[base], vols, kw["Class"]):
        if c.strip() == "Exclude":
            continue
        term = (b or k).strip()
        rows.append((k, term, int(v), set(term_tokens(term))))
    return rows


def split_terms(topic):
    return [t.strip() for t in re.split(r"[;|]", topic) if t.strip()]


def topic_candidates(topic, kwrows):
    """Keywords that fit a page topic. A keyword fits a topic term when it has all the term's words (best), or, for a
    term of several words, the term's rarest word (only when that word is in the list at all, so a word the list has
    never seen cannot fall back on the common word next to it). Returns ([(term, volume)], {term: groups with all words})."""
    full, part, cov = [], [], {}
    for term in split_terms(topic):
        toks = set(term_tokens(term))
        if not toks:
            continue
        cnt = {t: sum(1 for r in kwrows if t in r[3]) for t in toks}
        rare = min(toks, key=lambda t: (cnt[t], t))
        f = [(r[0], r[1], r[2]) for r in kwrows if toks <= r[3]]
        cov[term] = len({dedupe_key(r[1]) for r in f})
        full += f
        if len(toks) > 1 and cnt[rare] > 0:
            part += [(r[0], r[1], r[2]) for r in kwrows if rare in r[3] and not toks <= r[3]]
    out = ranked(full)[:MAX_TOPIC]
    seen = {dedupe_key(t) for t, _ in out}
    for t, v in ranked(part):
        if len(out) >= MAX_TOPIC:
            break
        if dedupe_key(t) not in seen:
            out.append((t, v))
            seen.add(dedupe_key(t))
    return out, cov


def read_topics(path, pages):
    """work/topics.tsv: id <TAB> topic <TAB> optional 'none' (the taxonomy's guess is wrong for this page)."""
    topics, ids = {}, {p["id"] for p in pages}
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
            mark = parts[2].lower() if len(parts) > 2 else ""
            if mark not in ("", "none"):
                sys.exit(f"{path}: id {i}: third column must be empty or 'none', not '{parts[2]}'")
            topics[i] = (topic, mark == "none")
    missing = sorted(i for i in ids if not topics.get(i, ("", False))[0])
    if missing:
        sys.exit(f"{path}: no topic for page ids {missing[:20]}{' ...' if len(missing) > 20 else ''}. Every page needs one.")
    return topics


def read_strikes(path):
    """work/strikes.tsv: id <TAB> candidate numbers to drop, comma separated."""
    out = {}
    if not path:
        return out
    with open(path, encoding="utf-8-sig") as fh:
        for line in fh:
            parts = [x.strip() for x in line.rstrip("\n").split("\t")]
            if len(parts) < 2 or not parts[0].isdigit():
                continue
            nums = set()
            for a, b in re.findall(r"(\d+)(?:\s*-\s*(\d+))?", parts[1]):  # "3", "2-6"
                nums.update(range(int(a), int(b or a) + 1))
            out[int(parts[0])] = nums
    return out


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

def short(s, n=80):
    s = " ".join(s.split())
    return s if len(s) <= n else s[:n - 1] + "…"


def cmd_inspect(args):
    pages, cols, dups = load_crawl(args)
    entries, _ = load_taxonomy(args.taxonomy)
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "urls.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(p["url"] for p in pages) + "\n")
    with open(os.path.join(args.out, "pages.tsv"), "w", encoding="utf-8") as fh:
        fh.write("id\tpath\th1\ttitle\ttaxonomy guess\n")
        for i, p in enumerate(pages, 1):
            e, _, _ = resolve_page(p, entries)
            fh.write(f"{i}\t{p['path']}\t{short(p['h1'])}\t{short(p['title'].split('|')[0])}\t"
                     f"{e.level + ': ' + e.label if e else '-'}\n")
    print(f"Columns used: URL='{cols[0]}', H1='{cols[1]}', Title='{cols[2]}'")
    print(f"Pages: {len(pages)} (duplicate URLs skipped: {dups}); blank H1: {sum(not p['h1'] for p in pages)}; "
          f"blank title: {sum(not p['title'] for p in pages)}")
    print(f"Wrote {os.path.join(args.out, 'urls.txt')} and {os.path.join(args.out, 'pages.tsv')}")


def prepare(args, pages, entries, pools, kwrows):
    """Apply the AI's topics: taxonomy entry (only if the AI did not reject it), candidate keywords per page,
    implied entries with no page. Used by both candidates and build so the numbering is identical."""
    for i, p in enumerate(pages, 1):
        p["id"] = i
    topics = read_topics(args.topics, pages)
    for p in pages:
        p["entry"], p["field"], p["reason"] = resolve_page(p, entries)
        p["guess"] = p["entry"]
        p["topic"], rejected = topics[p["id"]]
        if rejected:
            p["entry"] = None
    has_page = {p["entry"].key for p in pages if p["entry"]}
    recs, unresolved = {}, defaultdict(set)
    for p in pages:
        p["notes"], p["flags"] = [], []
        p["cands"], p["cov"] = topic_candidates(p["topic"], kwrows)
        p["cands"] = [(t, v, "") for t, v in p["cands"]]
        e = p["entry"]
        if not e:
            continue
        found, missing = implied_entries(e, entries)
        for n in missing:
            unresolved[n].add(e.label)
        borrowed, used = [], {dedupe_key(t) for t, _, _ in p["cands"]}
        for imp in found:
            if imp.key in has_page or imp.blocked():
                continue
            for t, v in ranked(pools.get(imp.key, []))[:MAX_BORROW]:
                borrowed.append((t, v, imp.label))
            if e.level != "Concern":  # a Concern never proves the service is offered
                r = recs.setdefault(imp.key, {"entry": imp, "by": {}})
                r["by"][p["url"]] = e.label
        for t, v, lab in sorted(borrowed, key=lambda x: -x[1]):
            if sum(1 for c in p["cands"] if c[2]) >= MAX_BORROW:
                break
            if dedupe_key(t) not in used:
                p["cands"].append((t, v, f"from {lab}, which has no page"))
                used.add(dedupe_key(t))
    return recs, unresolved


def cmd_candidates(args):
    pages, _, _ = load_crawl(args)
    entries, pools = load_taxonomy(args.taxonomy)
    kwrows = load_keyword_rows(args.taxonomy)
    prepare(args, pages, entries, pools, kwrows)
    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, "candidates.txt")
    with open(path, "w", encoding="utf-8") as fh:
        for p in pages:
            fh.write(f"[{p['id']}] {p['topic']}\n")
            for n, (t, v, tag) in enumerate(p["cands"], 1):
                fh.write(f"  {n}. {t} - {v:,}{'  (' + tag + ')' if tag else ''}\n")
            low = [f'"{t}" ({c})' for t, c in p["cov"].items() if c < FEW]
            if low:
                fh.write("  few or none in the list: " + ", ".join(low) + "\n")
            if not p["cands"]:
                fh.write("  (no candidates)\n")
    print(f"Wrote {path}: {len(pages)} pages, {sum(len(p['cands']) for p in pages)} candidates")


def cmd_build(args):
    pages, cols, dups = load_crawl(args)
    entries, pools = load_taxonomy(args.taxonomy)
    kwrows = load_keyword_rows(args.taxonomy)
    gsc = load_gsc(args.gsc) if args.gsc else None
    cities = [c.strip() for c in (args.cities or "").split(",") if c.strip()]
    city_keys = {term_key(c) for c in cities}
    print(f"Pages: {len(pages)} (duplicates skipped {dups}); taxonomy entries: {len(entries)}")
    print("GSC: " + ("used" if gsc is not None else "not used (no --gsc): no clicks or impressions, export order"))
    print("City check: " + (", ".join(cities) if cities else "skipped (no --cities)"))

    # 1-2. the AI's topic for each page, the candidate keywords, entries with no page
    recs, unresolved = prepare(args, pages, entries, pools, kwrows)
    strikes = read_strikes(args.strikes)
    bad = [(i, n) for i, ns in strikes.items() for n in ns
           if i not in {p["id"] for p in pages} or n < 1 or n > len(next(p for p in pages if p["id"] == i)["cands"])]
    if bad:
        sys.exit(f"{args.strikes}: strike numbers that are not candidates (page id, number): {bad[:10]}")
    print(f"Strikes applied on {len(strikes)} pages ({sum(len(v) for v in strikes.values())} keywords)")

    missing_terms = defaultdict(lambda: [None, 0, []])  # term -> [term, groups found, urls]
    for p in pages:
        gone = strikes.get(p["id"], set())
        kept = [(t, v) for n, (t, v, _) in enumerate(p["cands"], 1) if n not in gone]
        p["lines"] = sorted(kept, key=lambda x: -x[1])[:5]
        low = [(t, c) for t, c in p["cov"].items() if c < FEW]
        if low:
            p["flags"].append(("fewkw", "Few or no keywords in the taxonomy keyword list for: " +
                               ", ".join(f'"{t}" ({"none" if c == 0 else str(c) + " found"})' for t, c in low)))
            for t, c in low:
                m = missing_terms[t.lower()]
                m[0], m[1] = t, c
                m[2].append(p["url"])
        if not p["lines"]:
            p["flags"].append(("nokeywords", "No relevant keywords left for this topic. Choose them by hand"))
        if p["entry"]:
            p["notes"].append(f"Taxonomy: {p['entry'].level}: {p['entry'].label}, matched on {p['field']}")
            added = sorted({tag[5:].split(",")[0] for _, _, tag in p["cands"] if tag})
            if added:
                p["notes"].append("Also offered keywords of entries with no page in the crawl: " + "; ".join(added))
        elif p["guess"]:
            p["notes"].append(f"Taxonomy guessed {p['guess'].label}; the topic says otherwise")

    # 3. what the current Title Tag and H1 already say
    for p in pages:
        if not p["h1"]:
            p["flags"].append(("blankh1", "Blank H1"))
        if not p["title"]:
            p["flags"].append(("blanktitle", "Blank Title Tag"))
        have = phrase_keys(p["title"]) | phrase_keys(p["h1"])
        if p["lines"] and not any(term_key(t) in have for t, _ in p["lines"]):
            p["flags"].append(("notrep", "None of the top keywords appear in the Title Tag or H1"))
        if city_keys and not (city_keys & have):
            p["flags"].append(("nocity", "No city in the Title Tag or H1"))

    # 4. merge GSC (optional)
    crawl_keys = {p["key"] for p in pages}
    if gsc is not None:
        matched_gsc = 0
        for p in pages:
            g = gsc.get(p["key"])
            p["clicks"], p["impr"] = (int(g[0]), int(g[1])) if g else (0, 0)
            if g:
                matched_gsc += 1
            else:
                p["notes"].append("No GSC data")
        rate = matched_gsc / len(pages) if pages else 0
        extra = sum(1 for k in gsc if k not in crawl_keys)
        print(f"GSC rows matched to crawled pages: {matched_gsc}/{len(pages)} ({rate:.0%}); GSC rows not in crawl: {extra}")
        if rate < 0.5:
            print("WARNING: under half the pages matched a GSC row. Check the property, the date range and the URL form "
                  "(http/https, www, trailing slash) before trusting the metrics.")

    # 5. workbook
    gcols = ["GSC Clicks", "GSC Impressions"] if gsc is not None else []
    head = (["URL", "Review Needed", "Why Review", "Page Topic", "Current Page Title", "Current H1",
             "Suggested Page Title", "Suggested H1", "Update to Include"] + gcols + ["Matching Notes"])
    width = {"URL": 45, "Review Needed": 11, "Why Review": 42, "Page Topic": 28, "Current Page Title": 40,
             "Current H1": 36, "Suggested Page Title": 40, "Suggested H1": 36, "Update to Include": 38,
             "GSC Clicks": 11, "GSC Impressions": 13, "Matching Notes": 45}
    ordered = sorted(pages, key=lambda x: (-x["clicks"], -x["impr"], x["url"])) if gsc is not None else pages
    review = []
    for p in ordered:
        row = [p["url"], "Yes" if p["flags"] else "No", "\n".join(t for _, t in p["flags"]), p["topic"],
               p["title"], p["h1"], None, None, "\n".join(f"{t} - {v:,}" for t, v in p["lines"])]
        if gsc is not None:
            row += [p["clicks"], p["impr"]]
        row.append(" | ".join(p["notes"]))
        review.append(row)
    rec_rows = []
    order = {"Service": 0, "Sub-Service": 1, "Brand / Device": 2}
    for r in sorted(recs.values(), key=lambda r: (order[r["entry"].level], r["entry"].label)):
        labels = sorted(set(r["by"].values()))
        rec_rows.append([r["entry"].label, r["entry"].level, "\n".join(r["by"]),
                         f"Implied by the {', '.join(labels)} page; no crawled page maps to {r['entry'].label}."])
    if not rec_rows:
        rec_rows = [["None", "", "", "No implied page is missing from the crawl."]]
    dhead = ["URL", "Page Path", "H1", "Title Tag"] + gcols
    data = [[p["url"], p["path"], p["h1"], p["title"]] + ([p["clicks"], p["impr"]] if gsc is not None else [])
            for p in pages]

    wb = Workbook()
    ws = add_sheet(wb, True, "Review", head, review, [width[h] for h in head],
                   numeric=("GSC Clicks", "GSC Impressions"), yellow=("Suggested Page Title", "Suggested H1"))
    ws.cell(1, head.index("Update to Include") + 1).comment = Comment(
        "Volume comes from competitor rankings, often in other markets. Use it to rank keywords against each "
        "other, not as demand for this client.", "Mavan")
    for cell in ws[get_column_letter(2)][1:]:
        if cell.value == "Yes":
            cell.fill = PatternFill("solid", fgColor="F8CBAD")
    add_sheet(wb, False, "Recommendations", ["Recommended Page", "Level", "Implied By (URL)", "Reason"],
              rec_rows, [38, 16, 55, 70])
    add_sheet(wb, False, "Data", dhead, data, [{"URL": 45, "Page Path": 36, "H1": 36, "Title Tag": 40, "GSC Clicks": 11,
                                                "GSC Impressions": 13}[h] for h in dhead],
              numeric=("GSC Clicks", "GSC Impressions"))
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    wb.save(args.out)
    print(f"Saved {args.out}")

    # the topics the keyword list does not cover, for Amanda to add
    miss_path = os.path.splitext(args.out)[0] + "_missing_keywords.csv"
    if missing_terms:
        with open(miss_path, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["Topic", "Keywords found in the list", "Pages (URL)"])
            for t, c, urls in sorted(missing_terms.values(), key=lambda m: m[0].lower()):
                w.writerow([t, c, "\n".join(urls)])
        print(f"Missing-keywords list: {len(missing_terms)} topics -> {miss_path}")
    else:
        if os.path.exists(miss_path):
            os.remove(miss_path)
        print("Missing-keywords list: none needed")

    # 6. summary and QA
    by_level = defaultdict(int)
    for p in pages:
        by_level[p["entry"].level if p["entry"] else "No taxonomy entry"] += 1
    print("Pages by taxonomy entry level:", dict(by_level))
    by_flag = defaultdict(int)
    for p in pages:
        for code, _ in p["flags"]:
            by_flag[code] += 1
    print(f"Review Needed = Yes on {sum(1 for p in pages if p['flags'])} of {len(pages)} pages; flags: {dict(by_flag)}")
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
    checks.append(("Every page has a topic", all(p["topic"] for p in pages)))
    checks.append(("Every page with no keywords is marked Review Needed = Yes", all(p["flags"] for p in pages if not p["lines"])))
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
    for name in ("inspect", "candidates", "build"):
        sp = sub.add_parser(name)
        sp.add_argument("--crawl", required=True, help="Screaming Frog or Sitebulb export (CSV or xlsx)")
        sp.add_argument("--url-col")
        sp.add_argument("--h1-col")
        sp.add_argument("--title-col")
        sp.add_argument("--taxonomy", default=DEFAULT_TAXONOMY)
        sp.add_argument("--out", required=True, help="inspect, candidates: work folder. build: output .xlsx path")
        if name in ("candidates", "build"):
            sp.add_argument("--topics", required=True, help="work/topics.tsv written from the AI's reading of work/pages.tsv")
        if name == "build":
            sp.add_argument("--strikes", help="work/strikes.tsv: candidate numbers the AI dropped, e.g. 1,4 or 2-6. Optional")
            sp.add_argument("--gsc", help="folder (or file) of saved GSC rows, .json or .csv. Optional: without it the workbook has no clicks or impressions")
            sp.add_argument("--cities", help="the client's city or service-area cities, comma separated. Optional: without it the city check is skipped")
    args = ap.parse_args()
    {"inspect": cmd_inspect, "candidates": cmd_candidates, "build": cmd_build}[args.cmd](args)


if __name__ == "__main__":
    main()
