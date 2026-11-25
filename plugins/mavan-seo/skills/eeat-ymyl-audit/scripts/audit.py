#!/usr/bin/env python3
"""E-E-A-T & YMYL audit.

  python audit.py preflight --config config.json --crawl crawl.csv --outlinks outlinks.csv --out work [--external external.csv] [--chrome work/chrome.tsv]
  python audit.py queue     --config config.json --crawl crawl.csv --outlinks outlinks.csv --external external.csv --out work
                            [--types Condition,Service] [--max N] [--max-per-type N]
  python audit.py build     --config config.json --crawl crawl.csv --outlinks outlinks.csv --external external.csv
                            --chrome work/chrome.tsv [--claims work/claims.tsv] [--types ...] [--max N] --out audit.xlsx

preflight: checks the config and the exports, prints what is ready, what is a warning and what stops the build, writes
           work/external_urls.txt (the deduped external destinations to crawl in list mode) and shows the start and end of the body
           text of one page per page type so the person can see whether the content selector is right. With --chrome it also prints
           what the crawl detected on each page Claude in Chrome checked, so Claude can fill in the "agrees" column.
queue:     lists the pages for the accuracy review and writes each page's body text to work/text/ for the AI to read.
build:     builds the workbook. Every count and join happens here. Rules: references/rules.md.
The AI never types a number. It reads body text only for the accuracy review (queue) and writes claims.tsv / chrome.tsv.
"""
import argparse
import csv
import json
import os
import random
import re
import sys
import unicodedata
from collections import Counter
from urllib.parse import unquote, urlsplit

import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.table import Table, TableStyleInfo

URL_NAMES = ["address", "url", "page url"]
STATUS_NAMES = ["status code", "http status code", "status"]
INDEX_NAMES = ["indexability", "indexable status", "indexable"]
OL_SOURCE = ["source", "from", "source url", "source page", "referring url", "linking url", "page url"]
OL_DEST = ["destination", "to", "destination url", "link url", "target url", "link destination"]
OL_ANCHOR = ["anchor", "anchor text", "link text"]
OL_POS = ["link position", "position", "link location", "location"]
OL_TYPE = ["type", "link type"]
OL_STATUS = ["status code", "http status code"]
EXT_TITLE = ["title 1", "title", "page title"]
EXT_H1 = ["h1-1", "h1", "h1 1"]

DEFAULT_CREDENTIALS = ["MD", "DO", "DDS", "DMD", "NP", "PA", "PA-C", "RN", "PhD", "FACS", "FAAD", "board-certified", "board certified"]
BLOCKED = {401, 403, 405, 429, 999}
STOP_WORDS = set("a an and or the of in on for to with by at as is are be from vs near me your you our we it its this that these those into".split())
GENERIC_WORDS = set("click here read more link article source sources page website site learn see visit via official research study studies shows show according report info information".split())
FLAGGED = ["Dead link", "No response", "No shared words"]
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
    host = host_of(u)
    if not re.match(r"^[a-z][a-z0-9+.-]*://", u, re.I):
        u = "//" + u
    p = urlsplit(u)
    path = unquote(p.path or "/")
    if len(path) > 1:
        path = path.rstrip("/")
    return (host + path + ("?" + p.query if p.query else "")).lower()


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
    cfg.setdefault("content_link_positions", ["Content"])
    for k in ("experience_terms", "own_domains", "credential_terms"):
        cfg.setdefault(k, [])
    if not cfg["columns"].get("body"):
        findings.append(("STOP", "Config has no columns.body: the crawl column that holds each page's body text."))
    rules = cfg.get("page_types") or []
    if not rules:
        findings.append(("STOP", "Config has no page_types: which pages are conditions, services, blogs and so on."))
    src = cfg.get("page_type_source") or {}
    if src and not (src.get("column") or (src.get("file") and src.get("url_column") and src.get("type_column"))):
        findings.append(("STOP", "page_type_source needs either column, or file with url_column and type_column."))
    for r in rules:
        r.setdefault("paths", [])
        r.setdefault("labels", [])
        if not r.get("name") or not (r["paths"] or src):
            findings.append(("STOP", f"Page type {r.get('name', '?')} needs a name, and paths unless page_type_source labels the pages."))
    return cfg


def load_labels(cfg, crawl, ucol, findings):
    """URL -> page type label from the IA / prune workbook or a label column in the crawl. None when not configured."""
    src = cfg.get("page_type_source") or {}
    if not src:
        return None
    if src.get("column"):
        col = resolve(crawl, src["column"], "page type label", findings)
        if not col:
            return {}
        return {norm_url(u): clean_text(t) for u, t in zip(crawl[ucol], crawl[col]) if str(u).strip() and clean_text(t)}
    try:
        if src["file"].lower().endswith((".xlsx", ".xlsm")):
            df = pd.read_excel(src["file"], sheet_name=src.get("sheet") or 0, dtype=str).fillna("")
            df.columns = [str(c).strip() for c in df.columns]
        else:
            df = read_table(src["file"])
    except Exception as e:
        findings.append(("STOP", f"Cannot read the page type file {src['file']}: {e}"))
        return {}
    uc = resolve(df, src["url_column"], "page type file URL", findings)
    tc = resolve(df, src["type_column"], "page type file type", findings)
    if not (uc and tc):
        return {}
    return {norm_url(u): clean_text(t) for u, t in zip(df[uc], df[tc]) if str(u).strip() and clean_text(t)}


def is_blank(name):
    return not name or str(name).strip().lower() in {"", "none", "n/a", "not present"}


def join_numbered(df):
    """Sitebulb's "all matched items" writes one column per match (Body 1, Body 2, ...). Add a joined column per base name
    ("Body *") holding the matches in order, so a config can name "Body *"."""
    groups = {}
    for c in df.columns:
        m = re.fullmatch(r"(.+?)\s+(\d+)", c)
        if m:
            groups.setdefault(m.group(1), []).append((int(m.group(2)), c))
    for base, cols in groups.items():
        cols = [c for _, c in sorted(cols)]
        df[base + " *"] = df[cols].apply(lambda r: " ".join(v for v in r if str(v).strip()), axis=1)
    return df


def resolve(df, name, label, findings):
    """Return the real column for a config column name; None when the site does not have it."""
    if is_blank(name):
        return None
    lookup = {c.lower(): c for c in df.columns}
    if str(name).strip().lower() in lookup:
        return lookup[str(name).strip().lower()]
    findings.append(("STOP", f"Config names the {label} column '{name}' but the crawl export has no such column. Columns: {list(df.columns)}"))
    return None


def page_type(url, rules, labels=None):
    """A label from page_type_source wins (matched to a page type's name or labels); otherwise the URL path rules."""
    if labels is not None:
        lab = labels.get(norm_url(url), "").lower()
        if lab:
            for r in rules:
                if lab == r["name"].lower() or lab in {x.lower() for x in r["labels"]}:
                    return r["name"]
            return None
    path = path_of(url)
    for r in rules:
        if any(p.lower() in path for p in r["paths"]):
            return r["name"]
    return None


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


URL_NOISE = set("http https www com org net gov edu io co us uk html htm php aspx asp cfm index default amp articles article "
                "pages page content en go scripts".split())
SCHEMA_SKIP = {"ListItem", "Question", "Answer", "EntryPoint", "SearchAction"}


def url_words(u, path_only=False):
    """Words in a destination's host and path (no query string, no ids), for when the crawler cannot give its title or H1."""
    p = urlsplit(str(u).strip())
    text = p.path if path_only else p.netloc + " " + p.path
    return " ".join(w for w in words(unquote(text)) if w not in URL_NOISE and not any(ch.isdigit() for ch in w))


def schema_types(v):
    """When the schema extraction holds the JSON-LD itself (Sitebulb), keep only the @type names, in order, once each."""
    if v is None or "@type" not in v:
        return v
    found = re.findall(r"""["']@type["']\s*:\s*\[?\s*["']([^"']+)["']""", v)
    return ", ".join(dict.fromkeys(t for t in found if t not in SCHEMA_SKIP)) or v


CREDIBLE_TLDS = (".gov", ".edu", ".org", ".gov.uk", ".nhs.uk", ".ac.uk", ".gc.ca")
CREDIBLE_HOSTS = {  # medical journals, databases and reputable medical sites outside .gov / .edu / .org
    "nejm.org", "jamanetwork.com", "thelancet.com", "bmj.com", "nature.com", "sciencedirect.com", "springer.com",
    "link.springer.com", "wiley.com", "onlinelibrary.wiley.com", "journals.lww.com", "academic.oup.com", "cochranelibrary.com",
    "frontiersin.org", "mdpi.com", "karger.com", "tandfonline.com", "journals.sagepub.com", "cell.com", "jaad.org",
    "webmd.com", "medicalnewstoday.com", "healthline.com", "verywellhealth.com", "merckmanuals.com", "uptodate.com", "drugs.com",
}


def is_credible(url, cfg):
    """A credible source: .gov, .edu, .org (and national equivalents), a known medical journal or reputable medical site, or a host
    the config adds. Social, shop and booking links are not."""
    h = host_of(url)
    extra = {x.lower().lstrip(".") for x in cfg.get("credible_domains", [])}
    if any(h == x or h.endswith("." + x) for x in CREDIBLE_HOSTS | extra):
        return True
    return h.endswith(CREDIBLE_TLDS)


def anchor_match(anchor, dest_text):
    """Match / Partial / No match / Generic anchor / Not checked. Plain word overlap, no judgement."""
    aw = {stem(w) for w in words(anchor) if w not in STOP_WORDS | GENERIC_WORDS}
    if not aw:
        return "Generic anchor"
    dw = {stem(w) for w in words(dest_text)}
    if not dw:
        return "Not checked"
    hit = len(aw & dw)
    return "Match" if hit == len(aw) else ("Partial" if hit else "No match")


ROLES = ("condition", "service", "blog")
# Every check the audit makes. roles: page roles it applies to ("all" = every audited page). Priority, next step and handoff are
# the defaults written to the Recommendations tab (references/rules.md).
REQS = [
    dict(key="reviewer", label="Reviewer who is a medical professional", roles="all", priority="High", tab="All Pages",
         missing="No medical reviewer shown", sentence="do not show a reviewer who is a medical professional",
         next="SEO: get the reviewing provider's name and credentials from the client. Dev: add a medically reviewed by line to the page templates.",
         handoff="Dev"),
    dict(key="credible_source", label="External link to a credible medical source", roles="all", priority="High", tab="External Links Needed",
         missing="No credible external source", sentence="have no external link to a medical journal, .gov, .edu, .org or reputable medical site",
         next="SEO: choose a source and the anchor text for each page in External Links Needed. Dev: add the links.", handoff="Dev"),
    dict(key="credentials", label="Credentials or years of experience mentioned", roles="all", priority="Medium", tab="All Pages",
         missing="No credentials or experience mentioned", sentence="do not mention any credentials or years of experience",
         next="SEO: confirm the provider's credentials and years of experience. Content: add them to the page copy.", handoff="Content"),
    dict(key="author", label="Author shown", roles=("blog",), priority="Medium", tab="All Pages",
         missing="No author shown", sentence="do not show an author",
         next="SEO: confirm the author with the client. Dev: add an author byline with a bio link to the blog template.", handoff="Dev"),
    dict(key="published", label="Published date shown", roles=("blog",), priority="Low", tab="All Pages",
         missing="No published date", sentence="do not show a published date",
         next="Dev: show the published date on the blog template.", handoff="Dev"),
    dict(key="condition_schema", label="MedicalCondition schema", roles=("condition",), priority="Medium", tab="All Pages",
         missing="No MedicalCondition schema", sentence="do not use MedicalCondition schema",
         next="SEO: confirm the schema template. Dev: add MedicalCondition schema to the concern / condition template.", handoff="Dev"),
    dict(key="procedure_schema", label="MedicalProcedure schema", roles=("service",), priority="Medium", tab="All Pages",
         missing="No MedicalProcedure schema", sentence="do not use MedicalProcedure schema",
         next="SEO: confirm the schema template. Dev: add MedicalProcedure schema to the service template.", handoff="Dev"),
    dict(key="faq_schema", label="FAQPage schema on pages with FAQs", roles="faq", priority="Low", tab="All Pages",
         missing="FAQs without FAQPage schema", sentence="have FAQs but no FAQPage schema",
         next="Dev: output FAQPage schema from the FAQ section on every page that has one.", handoff="Dev"),
    dict(key="reviews", label="Reviews or testimonials", roles=("service", "condition"), priority="Medium", tab="All Pages",
         missing="No reviews or testimonials", sentence="show no reviews or testimonials",
         next="SEO: pick relevant reviews for each page. Content: add them to the pages.", handoff="Content"),
    dict(key="before_after", label="Before/after photos", roles=("service",), priority="Medium", tab="All Pages",
         missing="No before/after photos", sentence="show no before/after photos",
         next="SEO: collect consented before/after photos for each treatment from the client. Content: add them to the pages.", handoff="Content"),
    dict(key="rating", label="Google rating shown", roles=("service",), priority="Medium", tab="All Pages",
         missing="No Google rating shown", sentence="do not show the Google rating",
         next="Dev: add the Google rating to the service template.", handoff="Dev"),
]
REQ_BY_KEY = {r["key"]: r for r in REQS}


BODY_MARKER_KEYS = ("faq", "testimonials", "before_after", "rating")


def body_found(body, cfg):
    """config body_markers: a regular expression per marker, looked for in the body text when the crawl has no marker column or
    the column is empty. Lets a marker be added after the crawl when the element's text or code is in the body."""
    pats = {k: v for k, v in (cfg.get("body_markers") or {}).items() if k in BODY_MARKER_KEYS and v}

    def found(key, value):
        if key not in pats or (value is not None and present(value)):
            return value
        return "Found in body text" if re.search(pats[key], body) else ""
    return found


REQ_FOR_COLUMN = {"author": "author", "reviewer": "reviewer", "published": "published", "testimonials": "reviews",
                  "before_after": "before_after", "rating": "rating"}


def required_for(key, role):
    """Whether an extraction feeds a requirement of this page role. Schema and FAQ feed every role; updated date none."""
    if key in ("schema", "faq"):
        return True
    req = REQ_BY_KEY.get(REQ_FOR_COLUMN.get(key, ""))
    return bool(req) and (req["roles"] == "all" or role in req["roles"])


def role_of(ptype, cfg):
    for r in cfg["page_types"]:
        if r["name"] == ptype and r.get("role") in ROLES:
            return r["role"]
    n = ptype.lower()
    return "condition" if ("condition" in n or "concern" in n) else "service" if "service" in n else \
        "blog" if any(x in n for x in ("blog", "post", "article")) else "other"


def has_type(schema, name):
    return bool(schema) and re.search(r"\b" + name + r"\b", schema) is not None


def evaluate(p, role, credential_terms):
    """Yes / Missing / Not required (or Not checked when the crawl has no column for it) for every check."""
    out = {}
    for r in REQS:
        k = r["key"]
        if r["roles"] == "faq":
            applies = p["faq"] is not None and present(p["faq"])
        else:
            applies = r["roles"] == "all" or role in r["roles"]
        if not applies:
            out[k] = "Not required" if not (r["roles"] == "faq" and p["faq"] is None) else "Not checked"
            continue
        if k == "reviewer":
            ok = p["reviewer"] is not None and present(p["reviewer"]) and bool(term_hits(p["reviewer"], credential_terms))
        elif k == "credible_source":
            ok = bool(p["credible"])
        elif k == "credentials":
            ok = bool(p["creds"] or p["exp"])
        elif k in ("author", "published", "before_after", "rating"):
            ok = p[k] is not None and present(p[k])
        elif k == "reviews":
            ok = p["testimonials"] is not None and present(p["testimonials"])
        elif k in ("condition_schema", "procedure_schema", "faq_schema"):
            if p["schema"] is None:
                out[k] = "Not checked"
                continue
            ok = has_type(p["schema"], {"condition_schema": "MedicalCondition", "procedure_schema": "MedicalProcedure",
                                        "faq_schema": "FAQPage"}[k])
        out[k] = "Yes" if ok else "Missing"
    return out


# ------------------------------------------------------------------ analysis
def analyze(args, need_external):
    findings = []
    cfg = load_config(args.config, findings)
    try:
        crawl = read_table(args.crawl)
        # Sitebulb writes "Not Found" when a rule finds nothing and "Not Set" in unused match columns: treat both as empty.
        crawl = crawl.apply(lambda col: col.where(~col.str.strip().str.lower().isin({"not found", "not present", "not set"}), ""))
        crawl = join_numbered(crawl)
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
        findings.append(("STOP", "The export of the external destinations' status codes is missing (--external)."))

    c = cfg["columns"]
    ucol = resolve(crawl, c.get("url"), "url", findings) if c.get("url") else find_col(crawl, URL_NAMES)
    if not ucol:
        findings.append(("STOP", f"Crawl export has no URL column. Columns: {list(crawl.columns)}. Name it in config columns.url."))
    scol = resolve(crawl, c.get("status"), "status", findings) if c.get("status") else find_col(crawl, STATUS_NAMES)
    icol = resolve(crawl, c.get("indexability"), "indexability", findings) if c.get("indexability") else find_col(crawl, INDEX_NAMES)
    cols = {k: resolve(crawl, c.get(k), k, findings) for k in
            ("body", "author", "reviewer", "published", "updated", "schema", "testimonials", "before_after", "rating", "faq")}

    osrc, odst = find_col(outl, OL_SOURCE), find_col(outl, OL_DEST)
    oanc, opos, otype, ostat = (find_col(outl, n) for n in (OL_ANCHOR, OL_POS, OL_TYPE, OL_STATUS))
    if not (osrc and odst):
        findings.append(("STOP", f"Outlinks export needs a source and a destination column. Columns: {list(outl.columns)}"))
    if not oanc:
        findings.append(("STOP", f"Outlinks export has no anchor text column. Columns: {list(outl.columns)}"))
    if any(l == "STOP" for l, _ in findings):
        return dict(findings=findings, cfg=cfg)

    # ---- pages
    labels = load_labels(cfg, crawl, ucol, findings)
    if any(l == "STOP" for l, _ in findings):
        return dict(findings=findings, cfg=cfg)
    if labels is not None:
        known = {r["name"].lower() for r in cfg["page_types"]} | {x.lower() for r in cfg["page_types"] for x in r["labels"]}
        other = Counter(v for v in labels.values() if v.lower() not in known)
        if other:
            findings.append(("WARN", "Page type labels not in the audit (left out): " + ", ".join(f"{k} ({n})" for k, n in other.most_common())))
    own_hosts = {host_of(u) for u in crawl[ucol] if u} | {h.lower().lstrip(".") for h in cfg["own_domains"]}
    credential_terms = DEFAULT_CREDENTIALS + cfg["credential_terms"]
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
        ptype = page_type(url, cfg["page_types"], labels)
        if not ptype:
            unmatched.append(url)
            continue
        val = lambda k: clean_text(r[cols[k]]) if cols[k] else None
        body = val("body") or ""
        found = body_found(body, cfg)
        author, reviewer = val("author"), val("reviewer")
        cred_text = " ".join([body, author or "", reviewer or ""])
        p = dict(url=url, key=norm_url(url), ptype=ptype, body=body, words=len(body.split()),
                 author=author, reviewer=reviewer, published=val("published"), updated=val("updated"), schema=schema_types(val("schema")),
                 testimonials=found("testimonials", val("testimonials")), before_after=found("before_after", val("before_after")),
                 rating=found("rating", val("rating")), faq=found("faq", val("faq")),
                 creds=term_hits(cred_text, credential_terms), exp=experience_hits(body, cfg), links=[])
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
        es, et, eh = find_col(ext, STATUS_NAMES), find_col(ext, EXT_TITLE), find_col(ext, EXT_H1)
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
        if title or h1:
            compared, match = "Title and H1", anchor_match(r[oanc], title + " " + h1)
        elif url_words(dst, path_only=True):  # Sitebulb only status-checks external URLs: infer from the destination URL
            compared, match = "URL", anchor_match(r[oanc], url_words(dst))
        else:  # the URL is only a host and an id (pubmed.ncbi.nlm.nih.gov/18462427): nothing to compare
            compared, match = "URL", "Not checked"
        flags = []
        if status >= 400 and status not in BLOCKED:
            flags.append("Dead link")
        elif status == 0:
            flags.append("No response")
        if match == "No match":
            flags.append("No shared words")
        if status in BLOCKED:
            flags.append("Check manually")
        row = dict(src=pages[src]["url"], pkey=src, anchor=clean_text(r[oanc]), dest=dst, status=status, title=title, h1=h1,
                   compared=compared, match=match, flags=flags, flagged=[f for f in flags if f in FLAGGED],
                   credible=is_credible(dst, cfg))
        pages[src]["links"].append(row)
        links.append(row)

    # ---- requirements by page role (references/rules.md): Yes / Missing / Not required
    for k in order:
        p = pages[k]
        p["cites"] = len(p["links"])
        p["credible"] = [l for l in p["links"] if l["credible"]]
        p["flagged_n"] = sum(1 for l in p["links"] if l["flagged"])
        p["checks"] = evaluate(p, role_of(p["ptype"], cfg), credential_terms)
        p["lacks"] = [REQ_BY_KEY[key]["missing"] for key, v in p["checks"].items() if v == "Missing"]

    # ---- findings
    n_pages = len(order)
    if not n_pages:
        findings.append(("STOP", "No crawled page matches any page type pattern in the config."))
    elif all(not pages[k]["body"] for k in order):
        findings.append(("STOP", "Body text is empty on every page: the content selector is wrong, or the site needs JavaScript rendering."))
    if not dest_urls and not any(l == "STOP" for l, _ in findings):
        findings.append(("STOP", "The outlinks export has no external links from these pages: external link crawling was off, or the link position setting excludes them all."))
    if ext is None and not need_external:
        findings.append(("WARN", "The external destinations' status codes are not in yet: export the external URLs with their HTTP status (Sitebulb: the external URLs export; Screaming Frog: a list-mode crawl of work/external_urls.txt), then re-run preflight with --external."))
    if n_pages:
        for lab, key in (("Body text", "body"), ("Author", "author"), ("Reviewer", "reviewer"), ("Published date", "published")):
            empty = [pages[k]["url"] for k in order if pages[k][key] is not None and not present(pages[k][key])]
            if empty:
                findings.append(("WARN", f"{lab} is empty on {len(empty)} of {n_pages} pages (first: {', '.join(empty[:3])}). If the pages do show it, the selector is wrong."))
        # An extraction that is empty on every page of a page type is more often a wrong selector than a site that lacks
        # the element. It must be checked in Claude in Chrome (work/checks.tsv) before the queue and the workbook.
        confirmed = load_checks(getattr(args, "checks", None), findings)
        for key in ("author", "reviewer", "published", "updated", "schema", "testimonials", "before_after", "rating", "faq"):
            if not cols[key]:
                continue
            for t in dict.fromkeys(pages[k]["ptype"] for k in order):
                tp = [k for k in order if pages[k]["ptype"] == t]
                if any(present(pages[k][key]) for k in tp):
                    continue
                if not required_for(key, role_of(t, cfg)):  # only what this page type needs is worth a check
                    continue
                hit = confirmed.get((cols[key].lower(), t.lower())) or confirmed.get((key, t.lower()))
                if hit:
                    findings.append(("OK", f"{cols[key]} is empty on all {len(tp)} {t} pages: confirmed absent in Claude in Chrome ({hit})."))
                else:
                    findings.append(("CHECK", f"{cols[key]} is empty on all {len(tp)} {t} pages (for example {pages[tp[0]]['url']}). "
                                              "Check the selector in Claude in Chrome before going on, then record it in work/checks.tsv."))
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
            findings.append(("WARN", f"{len(missing)} external destinations are not in the external URLs export (no status: shown as No response; first: {', '.join(missing[:3])})."))
        manual = sorted({l["dest"] for l in links if l["status"] in BLOCKED})
        if manual:
            findings.append(("WARN", f"{len(manual)} external destinations blocked the crawler (401, 403, 429 or 999) and need a manual check."))
    return dict(findings=findings, cfg=cfg, pages=pages, order=order, links=links, dest_urls=dest_urls)


def load_checks(path, findings):
    """work/checks.tsv: column, page_type, result, pages_checked. Only result "Confirmed absent" with the pages checked counts."""
    out = {}
    if not path:
        return out
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh, delimiter="\t"):
                if str(r.get("result", "")).strip().lower() == "confirmed absent" and str(r.get("pages_checked", "")).strip():
                    out[(str(r.get("column", "")).strip().lower(), str(r.get("page_type", "")).strip().lower())] = r["pages_checked"].strip()
    except OSError as e:
        findings.append(("STOP", f"Cannot read the checks file {path}: {e}"))
    return out


def print_findings(findings):
    for lvl, msg in findings:
        print(f"{'READY' if lvl == 'OK' else lvl}: {msg}")


def stop_if_needed(res):
    if any(l in ("STOP", "CHECK") for l, _ in res["findings"]):
        print_findings(res["findings"])
        sys.exit("STOP: fix the items above before building. Every CHECK needs a Claude in Chrome check recorded in work/checks.tsv (--checks).")


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
        per = Counter(res["pages"][k]["ptype"] for k in res["order"])
        print("Pages per page type: " + ", ".join(f"{r['name']} {per.get(r['name'], 0)}" for r in res["cfg"]["page_types"]))
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
        if args.chrome:
            print("What the crawl detected on the pages checked in Claude in Chrome:")
            for r in read_tsv(args.chrome, ["url"]):
                p = res["pages"].get(norm_url(r["url"]))
                print(f"  {r['url']}\n    " + (crawl_detected(p) if p else "NOT IN THE CRAWL (not an audited page: check the URL or the page type patterns)"))
            print()
    print_findings(res["findings"])
    if stops:
        sys.exit(1)


SAMPLE_MIN_WORDS = 200


def scoped(res, types=None, max_pages=None, per_type=None, sample=None):
    """Queued pages in crawl order: optionally some page types, N random pages of each type (the same pages on every run),
    the first N of each type, and N in all."""
    names = {t.strip().lower() for t in types.split(",")} if types else None
    order = res["order"]
    if sample:
        picked = set()
        for t in dict.fromkeys(res["pages"][k]["ptype"] for k in order):
            tp = [k for k in order if res["pages"][k]["ptype"] == t]
            full = [k for k in tp if res["pages"][k]["words"] >= SAMPLE_MIN_WORDS]  # hub and list pages make no claims
            pool = full if len(full) >= sample else tp
            picked |= set(random.Random(f"eeat-{t}").sample(pool, min(sample, len(pool))))
        order = [k for k in order if k in picked]
    out, seen = [], Counter()
    for k in order:
        p = res["pages"][k]
        if names and p["ptype"].lower() not in names:
            continue
        if per_type and seen[p["ptype"]] >= per_type:
            continue
        seen[p["ptype"]] += 1
        out.append(p)
    return out[:max_pages] if max_pages else out


def cmd_queue(args):
    res = analyze(args, need_external=True)
    stop_if_needed(res)
    for t in dict.fromkeys(res["pages"][k]["ptype"] for k in res["order"]):
        q = scoped(res, t)
        print(f"{t}: {len(q)} pages, {sum(p['words'] for p in q)} words of body text")
    q = scoped(res, args.types, args.max, args.max_per_type, args.sample_per_type)
    print(f"Queue: {len(q)} pages, {sum(p['words'] for p in q)} words of body text")
    tdir = os.path.join(args.out, "text")
    os.makedirs(tdir, exist_ok=True)
    with open(os.path.join(args.out, "queue.tsv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["id", "url", "page_type", "words", "external_citations"])
        for i, p in enumerate(q, 1):
            w.writerow([i, p["url"], p["ptype"], p["words"], p["cites"]])
            with open(os.path.join(tdir, f"{i:03d}.txt"), "w", encoding="utf-8") as t:
                t.write(f"URL: {p['url']}\nExternal citations on the page: {p['cites']}\n\n{p['body']}\n")
    print(f"Written to {args.out}/queue.tsv and {args.out}/text/")


# ------------------------------------------------------------------ workbook
FONT = "Arial"
HDR_FILL = PatternFill("solid", start_color="1F3864")
YELLOW = PatternFill("solid", start_color="FFF2CC")


def write_sheet(wb, title, header, rows, widths, yellow=(), name=None):
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
    if rows:
        t = Table(displayName=name or re.sub(r"\W", "", title), ref=f"A1:{get_column_letter(len(header))}{len(rows) + 1}")
        t.tableStyleInfo = TableStyleInfo(name="TableStyleLight1", showRowStripes=False)
        ws.add_table(t)
    return ws


def na(v, empty="None"):
    return "n/a" if v is None else (v or empty)


def yn(v):
    return "Not on this site" if v is None else ("Yes" if present(v) else "No")


def read_tsv(path, need):
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    for col in need:
        if not rows or col not in rows[0]:
            sys.exit(f"STOP: {path} needs the columns {need} and at least one row.")
    return rows


def crawl_detected(p):
    return "; ".join(f"{REQ_BY_KEY[k]['label']}: {v}" for k, v in p["checks"].items() if v != "Not required") + \
        f"; FAQ section: {yn(p['faq'])}; schema types: {na(p['schema'])}"


def split_claims(text):
    return [c.strip().strip('"').strip() for c in str(text or "").split("|") if c.strip().strip('"').strip()]


def add_list(ws, col, first, last, options):
    dv = DataValidation(type="list", formula1='"' + ",".join(options) + '"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(f"{col}{first}:{col}{max(first, last)}")


def plural(t, cfg=None):
    role = role_of(t, cfg) if cfg else ""
    return "blog posts" if role == "blog" else ("concern / condition pages" if role == "condition" else f"{t.lower()} pages")


def cmd_build(args):
    res = analyze(args, need_external=True)
    stop_if_needed(res)
    pages, order, links, cfg = res["pages"], res["order"], res["links"], res["cfg"]
    queue = scoped(res, args.types, args.max, args.max_per_type, args.sample_per_type)

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
    chrome = read_tsv(args.chrome, ["url", "visitor_sees", "agrees", "opportunities"])
    for r in chrome:
        if norm_url(r["url"]) not in pages:
            sys.exit(f"STOP: chrome.tsv has a URL that is not an audited page: {r['url']}")
        if r["agrees"] not in ("Yes", "Partly", "No"):
            sys.exit(f"STOP: chrome.tsv agrees must be Yes, Partly or No (the person's check of the sample page): {r['url']}")
        if r["agrees"] != "Yes":
            sys.exit(f"STOP: the person does not agree with what the crawl found on {r['url']}: fix the extraction and re-crawl first.")
    types = list(dict.fromkeys(pages[k]["ptype"] for k in order))
    checked = {pages[norm_url(r["url"])]["ptype"] for r in chrome}
    if set(types) - checked:
        sys.exit(f"STOP: the sample page check has no page for: {sorted(set(types) - checked)}")

    claim_rows = []
    for p in queue:
        cl = claims.get(p["key"])
        cited = "\n".join(l["dest"] for l in p["credible"]) or "None"
        if not cl:
            claim_rows.append([p["url"], p["ptype"], "Not read", cited, None, None, None, "Content"])
        for c in split_claims(cl["claims_to_verify"]) if cl and cl["specific_claims"] == "Yes" else []:
            claim_rows.append([p["url"], p["ptype"], c, cited, None, None, None, "Content"])
    need_links = [pages[k] for k in order if pages[k]["checks"]["credible_source"] == "Missing"]
    issue_links = [l for l in links if l["flags"]]

    wb = Workbook()
    wb.remove(wb.active)
    f10, b10 = Font(name=FONT, size=10), Font(name=FONT, size=10, bold=True)

    # ---- Recommendations: the rollup of every finding, with priority, owner and handoff
    ws = wb.create_sheet("Recommendations")
    r = 1
    ws.cell(r, 1, "E-E-A-T & YMYL audit: recommendations").font = Font(name=FONT, size=14, bold=True)
    r += 1
    ws.cell(r, 1, f"{len(order)} pages audited: " + ", ".join(f"{sum(1 for k in order if pages[k]['ptype'] == t)} {t}" for t in types)
            + f". {len(claim_rows)} claims to verify. Work the issues top to bottom; the Where to look tab has the page list.").font = f10
    r += 2

    def header(cols):
        nonlocal r
        for i, h in enumerate(cols, 1):
            c = ws.cell(r, i, h)
            c.font, c.fill = Font(name=FONT, bold=True, color="FFFFFF", size=10), HDR_FILL
            c.alignment = Alignment(wrap_text=True, vertical="center")

    def line(vals, yellow=()):
        nonlocal r
        r += 1
        for i, v in enumerate(vals, 1):
            c = ws.cell(r, i, v)
            c.font, c.alignment = f10, Alignment(wrap_text=True, vertical="top", horizontal="left")
            if i in yellow:
                c.fill = YELLOW

    issues = []
    for q in REQS:
        by_type = []
        for t in types:
            tp = [pages[k] for k in order if pages[k]["ptype"] == t]
            app = [p for p in tp if p["checks"][q["key"]] in ("Yes", "Missing")]
            miss = [p for p in app if p["checks"][q["key"]] == "Missing"]
            if miss:
                by_type.append((t, len(miss), len(app)))
        for t, x, y in by_type:
            what = (f"Across the board, {plural(t, cfg)} {q['sentence']} ({x} of {y})." if x == y
                    else f"{x} of {y} {plural(t, cfg)} {q['sentence']}.")
            issues.append(dict(priority=q["priority"], text=what, n=f"{x} of {y}", tab=q["tab"], next=q["next"], handoff=q["handoff"]))
    if claim_rows:
        nread = sum(1 for c in claim_rows if c[2] == "Not read")
        issues.append(dict(priority="High", text=f"{len(claim_rows) - nread} specific medical or factual claims on {len({c[0] for c in claim_rows})} pages need verifying against a real source"
                           + (f"; {nread} pages were not read" if nread else "") + ".",
                           n=str(len(claim_rows) - nread), tab="Claims Needing Verification",
                           next="SEO: verify each claim, mark it Accurate claim or Bad claim, add the source to cite and write the updated claim. Content: update the pages.",
                           handoff="Content"))
    # Claims are read on a sample. Where sampled blog or condition pages make 2+ claims while citing no credible source, the
    # rest of that content needs a closer claims review if the other changes do not bring improvements.
    for t in types:
        if role_of(t, cfg) not in ("blog", "condition"):
            continue
        tq = [p for p in queue if p["ptype"] == t and claims.get(p["key"])]
        unsourced = [(p, len(split_claims(claims[p["key"]]["claims_to_verify"]))) for p in tq
                     if not p["credible"] and claims[p["key"]]["specific_claims"] == "Yes"]
        n = sum(c for _, c in unsourced)
        total = sum(1 for k in order if pages[k]["ptype"] == t)
        if n >= 2 and len(tq) < total:
            issues.append(dict(priority="Low", text=f"The sampled {plural(t, cfg)} make {n} claims on {len(unsourced)} of {len(tq)} pages that cite no credible source. "
                                                     f"If the other changes do not bring improvements, the other {total - len(tq)} {plural(t, cfg)} need a closer review for claims.",
                               n=f"{len(unsourced)} of {len(tq)} sampled", tab="Claims Needing Verification",
                               next=f"SEO: after the other changes, check performance; if there is no improvement, have every {t.lower()} page read for claims and verified.",
                               handoff="Content"))
    dead = [l for l in issue_links if "Dead link" in l["flags"] or "No response" in l["flags"]]
    if issue_links:
        fl = Counter(f for l in issue_links for f in l["flags"])
        issues.append(dict(priority="High" if dead else "Medium",
                           text=f"{len(issue_links)} external links have an issue: " + ", ".join(f"{n} {f.lower()}" for f, n in fl.most_common()) + ".",
                           n=str(len(issue_links)), tab="External Link Issues",
                           next="SEO: choose Keep, Replace or Remove for each link and give the replacement URL and anchor. Dev: make the changes.",
                           handoff="Dev"))
    order_p = {"High": 0, "Medium": 1, "Low": 2}
    issues.sort(key=lambda i: order_p[i["priority"]])
    ws.cell(r, 1, "Issues found, by priority").font = b10
    r += 1
    cols = ["Priority", "Issue", "Pages / items", "Where to look", "Next steps (SEO / Dev / Content)", "Completion handoff", "Status"]
    header(cols)
    first = r + 1
    for i in issues:
        line([i["priority"], i["text"], i["n"], i["tab"], i["next"], i["handoff"], "Not started"], yellow=(7,))
    if not issues:
        line(["", "No issues found.", "", "", "", "", ""])
    add_list(ws, "G", first, r, ["Not started", "In progress", "Done"])
    r += 2

    ws.cell(r, 1, "Manual checks for the SEO").font = b10
    r += 1
    header(["What to check", "Where", "Items"])
    manual = [
        ("Choose a credible source and the anchor text for each page with no credible external link", "External Links Needed", len(need_links)),
        ("Decide Keep, Replace or Remove for each external link with an issue (blocked links need a look in a browser)", "External Link Issues", len(issue_links)),
        ("Verify each claim, set the claim status, add the source to cite and the updated claim", "Claims Needing Verification", len(claim_rows)),
        ("Confirm who reviews the content and their credentials, for the reviewer line", "Client", ""),
    ]
    for m in manual:
        if m[2] != 0:
            line(list(m))
    r += 2

    ws.cell(r, 1, "Ownership").font = b10
    r += 1
    header(["Owner", "Issues"])
    for owner in ("Dev", "Content"):
        line([owner, "\n".join(f"{i['priority']}: {i['text']}" for i in issues if i["handoff"] == owner) or "None"])
    r += 2

    warns = [m for l, m in res["findings"] if l == "WARN"] + [m for l, m in res["findings"] if l == "OK" and "confirmed absent" in m]
    ws.cell(r, 1, "Crawl notes").font = b10
    for m in warns or ["None"]:
        line([m])
    for i, w in enumerate([12, 70, 12, 24, 60, 14, 14], 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # ---- All Pages: reference sheet of every check on every page
    head = ["URL", "Page type"] + [q["label"] for q in REQS] + ["FAQ section", "Schema types", "Credentials found", "Years of experience",
                                                                  "External links", "Credible external links", "External links with an issue"]
    rows = []
    for k in order:
        p = pages[k]
        rows.append([p["url"], p["ptype"]] + [p["checks"][q["key"]] for q in REQS] +
                    [yn(p["faq"]), na(p["schema"]), ", ".join(p["creds"]) or "None", ", ".join(p["exp"]) or "None",
                     p["cites"], len(p["credible"]), p["flagged_n"]])
    write_sheet(wb, "All Pages", head, rows, [44, 12] + [13] * len(REQS) + [10, 30, 22, 16, 10, 10, 10], name="AllPages")

    # ---- External Links Needed (dev handoff)
    head = ["URL", "Page type", "External links on the page now (not credible)", "Claims on the page", "Source to link to",
            "Anchor text on the page", "Notes", "Completion handoff"]
    rows = []
    for p in need_links:
        cl = claims.get(p["key"])
        rows.append([p["url"], p["ptype"], "\n".join(l["dest"] for l in p["links"]) or "None",
                     " | ".join(split_claims(cl["claims_to_verify"]))[:500] if cl else "Not read", None, None, None, "Dev"])
    write_sheet(wb, "External Links Needed", head, rows, [44, 12, 40, 50, 40, 30, 30, 12], yellow=(5, 6, 7), name="LinksNeeded")

    # ---- External Link Issues (dev handoff)
    head = ["Source page", "Anchor text", "Destination URL", "Status", "Issue", "Anchor compared with", "Credible source",
            "Action", "Replacement URL", "New anchor text", "Notes", "Completion handoff"]
    rows = [[l["src"], l["anchor"], l["dest"], l["status"] or "No response", "; ".join(l["flags"]), l["compared"],
             "Yes" if l["credible"] else "No", None, None, None, None, "Dev"] for l in issue_links]
    ws2 = write_sheet(wb, "External Link Issues", head, rows, [40, 28, 46, 10, 26, 12, 10, 12, 40, 28, 30, 12], yellow=(8, 9, 10, 11), name="LinkIssues")
    add_list(ws2, "H", 2, len(rows) + 1, ["Keep", "Replace", "Remove"])

    # ---- Claims Needing Verification (content handoff)
    head = ["URL", "Page type", "Claim (page's own words)", "Credible sources the page cites now", "Source to cite", "Claim status",
            "Claim update", "Completion handoff"]
    ws3 = write_sheet(wb, "Claims Needing Verification", head, claim_rows, [40, 12, 60, 36, 40, 16, 50, 12], yellow=(5, 6, 7), name="Claims")
    add_list(ws3, "F", 2, len(claim_rows) + 1, ["Accurate claim", "Bad claim"])

    # ---- Sample Page Check
    head = ["Page type", "URL", "What the crawl detected", "What a visitor sees", "Person agrees with the crawl", "Other opportunities"]
    rows = []
    for cr in chrome:
        p = pages[norm_url(cr["url"])]
        rows.append([p["ptype"], p["url"], crawl_detected(p), cr["visitor_sees"], cr["agrees"], cr["opportunities"]])
    write_sheet(wb, "Sample Page Check", head, rows, [14, 44, 60, 60, 14, 60], name="SamplePageCheck")

    wb.save(args.out)
    qa(args.out, pages, order, links, need_links, issue_links, claim_rows, chrome, types)
    print(f"Saved {args.out}")


def qa(path, pages, order, links, need_links, issue_links, claim_rows, chrome, types):
    wb = load_workbook(path)
    ok = True

    def check(label, cond):
        nonlocal ok
        print(f"{'PASS' if cond else 'FAIL'}: {label}")
        ok = ok and cond

    ap = list(wb["All Pages"].iter_rows(min_row=2, values_only=True))
    check("every audited page appears once in All Pages", [r[0] for r in ap] == [pages[k]["url"] for k in order])
    ci = 2 + [q["key"] for q in REQS].index("credible_source")
    ln = list(wb["External Links Needed"].iter_rows(min_row=2, values_only=True))
    check("External Links Needed lists exactly the pages with no credible source",
          [r[0] for r in ln] == [r[0] for r in ap if r[ci] == "Missing"] == [p["url"] for p in need_links])
    li = list(wb["External Link Issues"].iter_rows(min_row=2, values_only=True))
    check("External Link Issues lists every flagged link once", len(li) == len(issue_links) == sum(1 for l in links if l["flags"]))
    cl = list(wb["Claims Needing Verification"].iter_rows(min_row=2, values_only=True))
    check("Claims Needing Verification has one row per claim", len(cl) == len(claim_rows))
    rec = [r for r in wb["Recommendations"].iter_rows(values_only=True) if r and r[0] in ("High", "Medium", "Low")]
    miss = sum(1 for r in ap for v in r[2:2 + len(REQS)] if v == "Missing")
    nums = [re.match(r"(\d+) of (\d+)", str(r[2])) for r in rec if r[3] in ("All Pages", "External Links Needed")]
    check("Recommendations counts add up to the Missing cells in All Pages", sum(int(m.group(1)) for m in nums if m) == miss)
    cc = list(wb["Sample Page Check"].iter_rows(min_row=2, values_only=True))
    check("every page type has a sample page the person checked", set(types) <= {r[0] for r in cc} and all(r[4] == "Yes" for r in cc))
    if not ok:
        sys.exit("QA failed")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("preflight", "queue", "build"):
        s = sub.add_parser(name)
        if name == "preflight":
            s.add_argument("--chrome")
        s.add_argument("--config", required=True)
        s.add_argument("--crawl", required=True)
        s.add_argument("--outlinks", required=True)
        s.add_argument("--external")
        s.add_argument("--checks")
        s.add_argument("--out", required=True)
        if name in ("queue", "build"):
            s.add_argument("--types")
            s.add_argument("--max", type=int)
            s.add_argument("--max-per-type", type=int, dest="max_per_type")
            s.add_argument("--sample-per-type", type=int, dest="sample_per_type")
        if name == "build":
            s.add_argument("--claims")
            s.add_argument("--chrome", required=True)
    args = ap.parse_args()
    {"preflight": cmd_preflight, "queue": cmd_queue, "build": cmd_build}[args.cmd](args)


if __name__ == "__main__":
    main()
