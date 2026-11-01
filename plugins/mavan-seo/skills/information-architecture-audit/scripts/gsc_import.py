#!/usr/bin/env python3
"""Load the blocks printed by ga4_workbench.py (saved as text files) and check their checksums.

Only GA4 comes through Composio now (table ga4 -> ga4.csv). Search Console comes from the Google Sheet through
gsc_sheet.py, which does not use this script.

Usage:
  python gsc_import.py --dir work/gsc

Every .txt file in --dir may hold one or more blocks from ##IA ... to ##END. Each block's row
count and CRC32 are checked; a block that fails was copied wrong and must be emitted and saved
again. Tables are written to <dir>/<table>.csv once all their parts are present and valid.
"""
import argparse
import csv
import glob
import os
import re
import sys
import zlib

ADDITIVE = {'pair_queries'}  # several rounds of pair queries add up (kept for old saved blocks)
HEAD = re.compile(r'^##IA table=(\w+) part=(\d+)/(\d+) rows=(\d+) crc=([0-9a-f]{8})\s*$')


def read_blocks(path):
    lines = open(path, encoding='utf-8').read().replace('\r\n', '\n').split('\n')
    i = 0
    while i < len(lines):
        m = HEAD.match(lines[i])
        if not m:
            i += 1
            continue
        try:
            end = lines.index('##END', i)
        except ValueError:
            yield m, None, None, f'{os.path.basename(path)}: block {m.group(1)} part {m.group(2)} has no ##END line'
            return
        header = lines[i + 1].split('|')
        body = lines[i + 2:end]
        yield m, header, body, None
        i = end + 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default='work/gsc')
    a = ap.parse_args()
    tables, errors = {}, []
    files = sorted(glob.glob(os.path.join(a.dir, '*.txt')))
    if not files:
        sys.exit(f'No .txt files in {a.dir}')
    for f in files:
        for m, header, body, err in read_blocks(f):
            if err:
                errors.append(err)
                continue
            name, part, total, rows, crc = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4)), m.group(5)
            text = '\n'.join(body)
            got = '%08x' % (zlib.crc32(text.encode('utf-8')) & 0xffffffff)
            where = f'{os.path.basename(f)}: {name} part {part}/{total}'
            if len(body) != rows:
                errors.append(f'{where}: expected {rows} rows, found {len(body)}. Emit and save it again.')
                continue
            if got != crc:
                bad = [n + 1 for n, ln in enumerate(body) if ln.count('|') != len(header) - 1]
                hint = f' Rows with the wrong number of fields: {bad[:10]}.' if bad else ''
                errors.append(f'{where}: checksum mismatch, so some text was copied wrong.{hint} Emit and save it again.')
                continue
            t = tables.setdefault(name, {'header': header, 'total': total, 'parts': {}})
            if name in ADDITIVE and part in t['parts']:
                t['parts'][part] = t['parts'][part] + [ln for ln in body if ln not in t['parts'][part]]
            else:
                t['parts'][part] = body
    done = []
    for name, t in tables.items():
        missing = [p for p in range(1, t['total'] + 1) if p not in t['parts']]
        if missing:
            errors.append(f'{name}: missing part(s) {missing} of {t["total"]}')
            continue
        out = os.path.join(a.dir, f'{name}.csv')
        with open(out, 'w', newline='', encoding='utf-8') as fh:
            w = csv.writer(fh)
            w.writerow(t['header'])
            for p in range(1, t['total'] + 1):
                for ln in t['parts'][p]:
                    w.writerow(ln.split('|'))
        done.append(f'{name} ({sum(len(b) for b in t["parts"].values())} rows)')
    print('Loaded:', ', '.join(done) if done else 'nothing')
    if errors:
        print('PROBLEMS:')
        for e in errors:
            print(' -', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
