"""Shared helpers (copied from the IA audit skill so this skill works on its own)."""
import json
import os
import re

# Keep identical to ia_norm() in gsc_workbench.py so crawl URLs and GSC URLs join.
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
