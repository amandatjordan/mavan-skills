#!/usr/bin/env python3
"""Save a Google Sheet downloaded through the Google Drive connector as an .xlsx file.

Usage:
  python save_drive_xlsx.py <download result> template.xlsx

<download result> is the file the Drive connector's download_file_content call was saved to
(its result is too large to show, so it lands in a tool-results file), or a file holding the
JSON it returned: {"content": "<base64>", "mimeType": ..., "title": ...}.
"""
import base64
import json
import sys

src, out = sys.argv[1], sys.argv[2]
raw = open(src, encoding='utf-8').read().strip()
try:
    data = json.loads(raw)
except json.JSONDecodeError:
    sys.exit(f'{src} is not the JSON the Drive connector returns.')
if isinstance(data, list):  # some clients wrap results in a list of content blocks
    data = json.loads(next(b['text'] for b in data if isinstance(b, dict) and 'text' in b))
blob = base64.b64decode(data['content'])
if not blob.startswith(b'PK'):
    sys.exit('Downloaded content is not an .xlsx file. Export with mimeType '
             'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.')
open(out, 'wb').write(blob)
print(f'Saved {data.get("title", "template")} to {out} ({len(blob):,} bytes)')
