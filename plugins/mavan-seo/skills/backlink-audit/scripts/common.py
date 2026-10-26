"""Shared helpers for the backlink audit scripts: loading tool exports, URLs and domains."""
import csv
import io
import json
import os
import re
from urllib.parse import urlparse

import pandas as pd

# Second-level suffixes where the registrable domain has three labels (example.co.uk).
MULTI_SUFFIX = {
    'co.uk', 'org.uk', 'ac.uk', 'gov.uk', 'me.uk', 'com.au', 'net.au', 'org.au', 'edu.au', 'gov.au',
    'co.nz', 'org.nz', 'co.za', 'com.br', 'com.mx', 'co.jp', 'co.in', 'co.kr', 'com.cn', 'com.tr',
    'com.sg', 'com.hk', 'co.il', 'com.ar', 'com.co', 'com.ph', 'com.my', 'co.id', 'com.pk', 'com.ua',
}


def canon(s):
    return re.sub(r'[^a-z0-9]', '', str(s).lower())


def read_table(path):
    """Read an Ahrefs/Semrush/GSC export: UTF-8, UTF-8 BOM or UTF-16, comma, tab or semicolon."""
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
    df = pd.read_csv(io.StringIO(text), sep=delim, dtype=str, keep_default_na=False,
                     quoting=csv.QUOTE_MINIMAL, engine='python')
    df.columns = [str(c).strip().strip('"') for c in df.columns]
    return df


def pick(df, aliases, required=False, label=''):
    """Return the column matching the first alias: exact canonical match first, then prefix."""
    cols = {canon(c): c for c in df.columns}
    for a in aliases:
        if canon(a) in cols:
            return cols[canon(a)]
    for a in aliases:
        for k, c in cols.items():
            if len(canon(a)) >= 4 and k.startswith(canon(a)):
                return c
    if required:
        raise SystemExit(f'{label}: none of the columns {aliases} found. Columns are: {list(df.columns)}. '
                         f'Pass --map {label}.FIELD="Column name" to set it.')
    return None


def resolve(df, spec, label, overrides):
    """spec = {field: (aliases, required)} -> {field: column or None}. Prints the mapping."""
    out = {}
    for field, (aliases, req) in spec.items():
        key = f'{label}.{field}'
        if key in overrides:
            if overrides[key] not in df.columns:
                raise SystemExit(f'--map {key}: column "{overrides[key]}" not in {list(df.columns)}')
            out[field] = overrides[key]
        else:
            out[field] = pick(df, aliases, req, label)
    found = ', '.join(f'{f}<-"{c}"' for f, c in out.items() if c)
    missing = [f for f, c in out.items() if not c]
    print(f'  {label}: {len(df):,} rows. {found}' + (f'. Not found: {", ".join(missing)}' if missing else ''))
    return out


def num(v):
    if v is None:
        return float('nan')
    s = str(v).strip().replace(',', '').replace('%', '')
    if s in ('', '-', 'n/a', 'N/A', 'null', 'None'):
        return float('nan')
    try:
        return float(s)
    except ValueError:
        return float('nan')


def truthy(v):
    return str(v).strip().lower() in ('true', '1', 'yes', 'y', 'nofollow', 'sitewide', 'x')


def bare_domain(d):
    d = str(d).strip().lower()
    d = re.sub(r'^[a-z]+://', '', d)
    d = d.split('/')[0].split(':')[0]
    return re.sub(r'^www\.', '', d)


def reg_domain(host_or_url):
    """Registrable domain: blog.example.com -> example.com, a.example.co.uk -> example.co.uk."""
    h = bare_domain(host_or_url)
    parts = [p for p in h.split('.') if p]
    if len(parts) <= 2:
        return h
    if '.'.join(parts[-2:]) in MULTI_SUFFIX:
        return '.'.join(parts[-3:])
    return '.'.join(parts[-2:])


def norm_url(u):
    """https, lowercase host, no www, no query or fragment, trailing slash on paths (not files)."""
    if not isinstance(u, str) or not u.strip():
        return ''
    u = u.strip()
    if u.startswith('//'):
        u = 'https:' + u
    if not re.match(r'^[a-z]+://', u, re.I):
        u = 'https://' + u
    p = urlparse(u)
    host = re.sub(r'^www\.', '', p.netloc.lower().split(':')[0])
    path = p.path or '/'
    if not path.endswith('/') and not re.search(r'/[^/]*\.[a-z0-9]{2,5}$', path, re.I):
        path += '/'
    return f'https://{host}{path.lower()}'


def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def save_json(path, obj):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)

