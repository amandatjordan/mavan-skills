"""Shared helpers for the IA audit scripts."""
import json
import os
import re

# Keep identical to ia_norm() in ga4_workbench.py so crawl URLs and GSC URLs join.
def normalize(u, domain):
    """lowercase, drop ?query and #fragment, https, no www, trailing slash (not on files)."""
    if not isinstance(u, str) or not u.strip():
        return ''
    u = u.strip().lower()
    u = re.sub(r'[?#].*$', '', u)
    if u.startswith('//'):
        u = 'https:' + u
    u = re.sub(r'^http://', 'https://', u)
    if not u.startswith('https://'):
        u = 'https://' + domain + ('' if u.startswith('/') else '/') + u
    u = re.sub(r'^https://www\.', 'https://', u)
    if not u.endswith('/') and not re.search(r'/[^/]*\.[a-z0-9]{2,5}$', u):
        u += '/'
    return u


def key(u, domain):
    """The path for the main domain (e.g. /services/botox/), the full URL for anything else."""
    n = normalize(u, domain)
    pre = 'https://' + domain
    return n[len(pre):] if n.startswith(pre + '/') else n


def has_query(u):
    return isinstance(u, str) and '?' in u


def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def save_json(path, obj):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)


def bare_domain(d):
    d = d.strip().lower()
    d = re.sub(r'^https?://', '', d)
    d = re.sub(r'^www\.', '', d)
    return d.split('/')[0]


# ---------- added for the migration sheet ----------
import io  # noqa: E402
import csv  # noqa: E402

import openpyxl  # noqa: E402
import pandas as pd  # noqa: E402

MEDIA_EXT = ('jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'avif', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
             'mp4', 'mov', 'zip', 'mp3')


def is_media(k):
    """True for a URL key that is a file (image, PDF, document) and not a page."""
    return bool(re.search(r'\.(' + '|'.join(MEDIA_EXT) + r')$', str(k).lower()))


def is_open(v):
    """True when a cell is still waiting for the SEO: empty, 'SEO fill in' or 'NEEDS TARGET ...'."""
    s = str(v or '').strip().lower()
    return s == '' or s.startswith('seo fill in') or s.startswith('needs target')


def read_table(path):
    """Read an Ahrefs, Semrush or Search Console export: UTF-8, UTF-8 BOM or UTF-16; comma, tab or semicolon."""
    raw = open(path, 'rb').read()
    if raw[:2] in (b'\xff\xfe', b'\xfe\xff'):
        text = raw.decode('utf-16')
    else:
        try:
            text = raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            text = raw.decode('latin-1')
    first = text.split('\n', 1)[0]
    delim = max([',', '\t', ';'], key=first.count)
    df = pd.read_csv(io.StringIO(text), sep=delim, dtype=str, keep_default_na=False, quoting=csv.QUOTE_MINIMAL, engine='python')
    df.columns = [str(c).strip().strip('"') for c in df.columns]
    return df


def workbook_tabs(path):
    """{tab name: list of rows (lists of stripped strings)} for an .xlsx workbook."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    out = {}
    for ws in wb.worksheets:
        out[ws.title] = [[('' if c is None else str(c).strip()) for c in r] for r in ws.iter_rows(values_only=True)]
    return out


def table(rows, first=None):
    """(headers, body rows). With `first`, the header row is the first row whose first cell starts with it.
    Without, headers are in row 1 when row 1 has several filled cells (the dev tab), else in row 2 (banner in row 1)."""
    if not rows:
        return [], []
    h = None
    if first:
        h = next((i for i, r in enumerate(rows[:6]) if r and r[0].lower().startswith(first.lower())), None)
    if h is None:
        h = 0 if sum(1 for c in rows[0] if c) >= 2 else 1
    if h >= len(rows):
        return [], []
    return rows[h], [r for r in rows[h + 1:] if any(r)]


def cell(r, i):
    return r[i] if i is not None and i < len(r) else ''


def col(headers, *starts):
    low = [h.lower() for h in headers]
    for s in starts:
        for i, h in enumerate(low):
            if h.startswith(s):
                return i
    return None
