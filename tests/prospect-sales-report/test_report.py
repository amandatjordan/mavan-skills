"""Prospect sales report: verdict priority, health scores, roadmap by track and tier, recurring band, GBP.

Run from the repo root:  python3 -m unittest discover -s tests/prospect-sales-report -v
"""
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / 'plugins/mavan-seo/skills/prospect-sales-report/scripts'
sys.path.insert(0, str(SCRIPTS))
import report  # noqa: E402


def lens(name, points, possible, severity):
    return {'lens': name, 'points': points, 'possible': possible, 'share': points / possible, 'severity': severity,
            'scored': 4}


def diagnosis(arch=('High', 4, 7), cont=('High', 4, 5), auth=('Medium', 2, 5)):
    return {
        'client': 'Example Spa', 'domain': 'example-spa.com', 'competitors': ['rival-one.com', 'rival-two.com'],
        'tool': ['Semrush'],
        'lenses': [lens('Authority', auth[1], auth[2], auth[0]), lens('Content', cont[1], cont[2], cont[0]),
                   lens('Architecture', arch[1], arch[2], arch[0])],
        'signals': [
            {'lens': 'Architecture', 'id': 'A1', 'points': 2, 'possible': 2,
             'data': {'archive': 600, 'indexable': 1000, 'share': 0.6}},
            {'lens': 'Architecture', 'id': 'A5', 'points': 0, 'possible': 1,
             'data': {'deep': 10, 'indexable': 1000, 'share': 0.01, 'depth': 3}},
            {'lens': 'Content', 'id': 'C1', 'points': 2, 'possible': 2,
             'data': {'competitor': 'rival-one.com', 'competitor_keywords': 900, 'prospect_keywords': 300, 'ratio': 3.0}},
            {'lens': 'Authority', 'id': 'U1', 'points': 0, 'possible': 2,
             'data': {'prospect': 25, 'median_competitor': 27, 'gap': 2}},
        ],
        'lead': [],
        'services': [{'service': 'Botox', 'keywords': 50, 'prospect_top10': 2, 'prospect_best': 4,
                      'top_competitor': 'rival-one.com', 'competitor_top10': 20, 'competitor_best': 1, 'lost': 15,
                      'note': ''}],
    }


class Verdict(unittest.TestCase):
    def test_architecture_wins_when_high_even_if_content_scores_higher(self):
        v, why = report.pick_verdict(diagnosis()['lenses'])
        self.assertEqual(v, 'Architecture')

    def test_content_when_architecture_not_high(self):
        v, _ = report.pick_verdict(diagnosis(arch=('Medium', 2, 7))['lenses'])
        self.assertEqual(v, 'Content')

    def test_highest_score_when_none_high(self):
        d = diagnosis(arch=('Low', 1, 7), cont=('Medium', 2, 5), auth=('Medium', 2, 4))
        v, why = report.pick_verdict(d['lenses'])
        self.assertEqual(v, 'Authority')
        self.assertIn('highest', why)

    def test_health_score(self):
        self.assertEqual(report.health(lens('Architecture', 4, 7, 'High')), 43)


class Roadmap(unittest.TestCase):
    def setUp(self):
        self.labels = report.load_labels()

    def test_only_verdict_track_and_tier(self):
        months, recurring, missing = report.roadmap('Site Architecture', 'starter', self.labels)
        titles = [t['title'] for m in months.values() for t in m]
        self.assertNotIn('Missing services review', titles)      # Service page gap audit is Signature only
        self.assertIn('Site structure overhaul', titles)
        self.assertEqual(missing, [])

    def test_recurring_band_and_badges(self):
        months, recurring, _ = report.roadmap('Authority & Trust', 'vip', self.labels)
        rec = [t for t, _ in recurring]
        self.assertIn('Account management', rec)
        self.assertNotIn('Account management', [t['title'] for t in months['Month 1']])
        badges = {t['title']: t['badge'] for t in months['Month 1']}
        self.assertEqual(badges['Link plan'], 'Start here')
        self.assertEqual(badges['Link building'], 'After: Link plan')

    def test_every_task_in_every_track_has_a_label(self):
        for track in ('Site Architecture', 'Poor Content', 'Authority & Trust', 'Google Maps'):
            for tier in ('starter', 'vip', 'signature'):
                _, _, missing = report.roadmap(track, tier, self.labels)
                self.assertEqual(missing, [], f'{track} {tier}')


def write_workbook(path, domain='example-spa.com', lead=()):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = 'Read Me'
    ws.append(['Item', 'Detail'])
    ws.append(['Prospect', f'Example Spa ({domain})'])
    v = wb.create_sheet('Verdict')
    v.append(['Lens', 'Severity', 'Score', 'Points', 'Lead issue', 'Evidence'])
    for name in ('Architecture', 'Content', 'Authority'):
        v.append([name, 'High', '50%', '1 of 2', 'Yes' if name in lead else '', ''])
    wb.create_sheet('Signals').append(['Lens'])
    wb.save(path)


class Page(unittest.TestCase):
    def run_report(self, d, *extra, cmd='build', tier='vip', workbook=True, wb_domain=None):
        tmp = Path(tempfile.mkdtemp())
        (tmp / 'diagnosis.json').write_text(json.dumps(d))
        args = [sys.executable, str(SCRIPTS / 'report.py'), cmd]
        if workbook:
            write_workbook(tmp / 'diag.xlsx', wb_domain or d['domain'], d.get('lead', []))
            args += ['--workbook', tmp / 'diag.xlsx']
        if tier:
            args += ['--tier', tier]
        out = tmp / 'report.html'
        args += ['--out', out if cmd == 'build' else tmp / 'work']
        p = subprocess.run([*map(str, args), *map(str, extra)], capture_output=True, text=True)
        return p, out

    def test_preflight_ready(self):
        p, _ = self.run_report(diagnosis(), cmd='preflight')
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertIn('READY', p.stdout)
        self.assertIn('WARN | Google Business Profile data', p.stdout)

    def test_preflight_needs_plan_level(self):
        p, _ = self.run_report(diagnosis(), cmd='preflight', tier=None)
        self.assertEqual(p.returncode, 2)
        self.assertIn('Proposed plan level', p.stdout)

    def test_preflight_needs_spreadsheet(self):
        p, _ = self.run_report(diagnosis(), cmd='preflight', workbook=False)
        self.assertEqual(p.returncode, 2)
        self.assertIn('Prospect diagnosis spreadsheet | not provided', p.stdout)

    def test_preflight_catches_mismatched_pair(self):
        p, _ = self.run_report(diagnosis(), cmd='preflight', wb_domain='other-spa.com')
        self.assertEqual(p.returncode, 2)
        self.assertIn('same run', p.stdout)

    def test_build_refuses_without_plan_level(self):
        p, out = self.run_report(diagnosis(), tier=None)
        self.assertEqual(p.returncode, 2)
        self.assertFalse(out.exists())

    def test_page_sections_and_no_codes(self):
        p, out = self.run_report(diagnosis())
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        page = out.read_text()
        for s in ('Site health score', 'Verdict', 'What we found', 'Recommended roadmap', 'Site Architecture track',
                  'Every month', 'Checked separately'):
            self.assertIn(s, page)
        self.assertIn('600 of your 1,000 indexable pages', page)
        self.assertNotIn('Poor Content track', page)
        self.assertIsNone(re.search(r'>\s*[ACU][1-6]\b', page))

    def test_gbp_included_in_overall(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / 'gbp.json').write_text(json.dumps({'score': 90, 'findings': [{'text': 'Profile complete', 'issue': False}]}))
        p, out = self.run_report(diagnosis(), '--gbp', tmp / 'gbp.json')
        page = out.read_text()
        self.assertIn('Profile complete', page)
        # 43, 20, 60 and 90 average to 53
        self.assertIn('aria-label="Score 53 out of 100"', page)

    def test_why_box_when_a_lower_score_is_not_the_verdict(self):
        p, out = self.run_report(diagnosis())          # Architecture 43 is the verdict, Content scores 20
        page = out.read_text()
        self.assertIn('Why we start here', page)
        self.assertIn('higher than Content (20)', page)
        self.assertIn('foundation', page)

    def test_no_why_box_when_verdict_is_lowest(self):
        p, out = self.run_report(diagnosis(arch=('High', 6, 7), cont=('High', 3, 5)))   # 14 vs 40
        self.assertNotIn('Why we start here', out.read_text())

    def test_maps_verdict_override_with_trust_clause(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / 'gbp.json').write_text(json.dumps({'score': 70, 'findings': [{'text': 'Few reviews', 'issue': True}]}))
        p, out = self.run_report(diagnosis(), '--gbp', tmp / 'gbp.json', '--verdict', 'maps')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        page = out.read_text()
        self.assertIn('Google Maps track', page)
        self.assertIn('not a major issue for you', page)     # Authority is Medium here

    def test_stops_without_any_issue(self):
        d = diagnosis(arch=('Low', 0, 7), cont=('Low', 0, 5), auth=('Low', 0, 5))
        p, _ = self.run_report(d)
        self.assertEqual(p.returncode, 2)
        self.assertIn('--verdict', p.stdout)

    def test_table_headers(self):
        _, out = self.run_report(diagnosis())
        page = out.read_text()
        self.assertIn('Your Rankings', page)
        self.assertIn("Competitor's", page)
        self.assertNotIn('page-one rankings</th>', page)


if __name__ == '__main__':
    unittest.main()
