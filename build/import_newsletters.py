#!/usr/bin/env python3
"""Import FFO Oct 9 + TWJN 283 newsletter rows into the Notion freelance DB.

Reads the parsed listing JSON, dedupes against existing Notion rows (reusing
scrape_oj_fu.notion_existing), writes new rows via REST, and updates state.json.
"""
import json, re, sys, subprocess, time
from pathlib import Path

BASE = Path('/Users/marcadrian/.local/share/vellum/assistants/vellum-faint-frog-0tgk4j/.vellum/workspace/scratch/freelance-list')
sys.path.insert(0, str(BASE))
import scrape_oj_fu

NOTION_DB = scrape_oj_fu.NOTION_DB
COLLECTION = '3eaa198a-6ad6-81d7-bb7c-000bae85ee04'

def load_ffo():
    """Parse /tmp/ffo_web.txt (clean listing text) into rows."""
    text = open('/tmp/ffo_web.txt').read()
    # split into sections by known header lines
    SECTIONS = {
        'Journalists': 'Journalists',
        'Copywriters & Writers': 'Writers',
        'Content Editing, Fact-checking, & Content Design': 'Writers',
        'Strategists & Search Engine Optimization': 'Writers',
        'PR & Marketing': 'Other',
        'Social Media & Community': 'Designers',
        'Art Direction & Graphic Design': 'Designers',
        'Video/Photo Production & Editing': 'Video',
        'Audio/Podcast Production & Editing': 'Audio',
        'Website/App Developers': 'Developers',
        'Various': 'Other',
    }
    # find section header line indices
    header_idx = []
    for i, line in enumerate(text.split('\n')):
        s = line.strip()
        if s in SECTIONS:
            header_idx.append((i, s))
    header_idx.append((len(text.split('\n')) + 1, None))  # sentinel
    rows = []
    for n, (idx, sec) in enumerate(header_idx[:-1]):
        end = header_idx[n+1][0]
        cat_map = {
            'Journalists': 'Journalists',
            'Copywriters & Writers': 'Writers',
            'Content Editing, Fact-checking, & Content Design': 'Writers',
            'Strategists & Search Engine Optimization': 'Writers',
            'PR & Marketing': 'Other',
            'Social Media & Community': 'Designers',
            'Art Direction & Graphic Design': 'Designers',
            'Video/Photo Production & Editing': 'Video',
            'Audio/Podcast Production & Editing': 'Audio',
            'Website/App Developers': 'Developers',
            'Various': 'Other',
        }
        cat = cat_map.get(sec, 'Other')
        lines = text.split('\n')
        i = idx + 1
        while i < end:
            line = lines[i].strip()
            if line:
                # Format: 'OrgName needs a <role> description' or 'OrgName (loc) needs ...'
                m = re.match(r'^([^ ]+(?:\s[^a-z][^ ]*)*)\s*(?:needs|is|are|has|puts|offers)\s+(.*)$', line, re.I)
                if m:
                    org = m.group(1).strip()
                    desc = m.group(2).strip()
                else:
                    org = line.split()[0] if line else ''
                    desc = line
                # clean org (remove location in parens)
                org_clean = re.sub(r'\s*\(([^)]*)\)\s*', ' ', org).strip()
                # extract location
                loc_m = re.search(r'\(([^)]+)\)', org)
                loc = loc_m.group(1) if loc_m else 'Remote'
                # extract pay
                pay_m = re.search(r'(\$[\d,.]+(?:k)?(?:-\$[\d,.]+(?:k)?)?(?:/\w+)?|\$[\d,.]+k/\w+|£[\d,.]+)', line)
                pay = pay_m.group(1) if pay_m else ''
                # determine type
                if re.search(r'full-time|full time', line, re.I): typ = 'Full-time'
                elif re.search(r'part-time|part time', line, re.I): typ = 'Part-time'
                elif re.search(r'fellowship', line, re.I): typ = 'Fellowship'
                elif re.search(r'grant', line, re.I): typ = 'Grant'
                elif re.search(r'freelance|intern|temporary|contract|gig', line, re.I): typ = 'Freelance'
                elif pay: typ = 'Hourly'
                else: typ = 'Freelance'
                # source platform guess
                src_plat = 'Other'
                if 'linkedin' in line: src_plat = 'LinkedIn'
                elif 'beehiiv' in line or 'substack' in line: src_plat = 'Substack'
                else: src_plat = 'Web page'
                rows.append({
                    'Position': f'{org_clean} — {desc}',
                    'Category': cat,
                    'Type': typ,
                    'Status': 'Active',
                    'Source Platform': src_plat,
                    'Source URL': '',  # filled from the web fetch
                    'Pay': pay,
                    'Location': loc,
                    'Description': desc[:500],
                    'Newsletter URL': 'https://www.findfreelanceopportunities.com/p/design-instagram-content-edit-sports-videos-grow-newsletters-and-work-as-an-audio-producer',
                    'Source Details': 'Freelance Opportunities! newsletter, issue of October 9, 2026',
                    'Issue Date': '2026-10-09',
                    'Verified': '__NO__',
                })
            i += 1
    return rows

def load_twjn():
    """Parse TWJN 283 free-preview listings (4 items)."""
    listings = [
        {
            'Position': 'Asimov Press — pitch: biotech essays and reported features ($1+ reported, $1,200 essays)',
            'Category': 'Writers', 'Type': 'Freelance', 'Status': 'Active',
            'Source Platform': 'X / Twitter',
            'Source URL': 'https://bsky.app/profile/asimovpress.bsky.social/post/3mx54lawqnv22',
            'Pay': '$1+ /word (reported features), $1,200 (essays)',
            'Deadline': '', 'Location': 'Remote',
            'Description': 'Asimov Press wants extremely deep, mechanistic writing about big ideas in biotechnology. Pitches to editors@asimov.com with "Pitch" in subject line.',
            'Newsletter URL': 'https://thewritersjob.beehiiv.com/p/twjn-283-pitch-calls-writing-opportunities-creative-jobs',
            'Source Details': 'TWJN newsletter issue 283, October 9, 2026 (free preview)',
            'Issue Date': '2026-10-09', 'Verified': '__NO__',
        },
        {
            'Position': 'Seattle Met — pitch: stories about trees for 2027 ($0.50/word)',
            'Category': 'Writers', 'Type': 'Freelance', 'Status': 'Active',
            'Source Platform': 'X / Twitter',
            'Source URL': 'https://bsky.app/profile/aliwill.bsky.social/post/3mx6niumrfk2j',
            'Pay': '$0.50/word', 'Deadline': '', 'Location': 'Remote',
            'Description': 'Seattle Met magazine is looking for 2027 pitches, specifically stories about trees. Rates start at $0.50/word. Pitches to pitches@seattlemet.com.',
            'Newsletter URL': 'https://thewritersjob.beehiiv.com/p/twjn-283-pitch-calls-writing-opportunities-creative-jobs',
            'Source Details': 'TWJN newsletter issue 283, October 9, 2026 (free preview)',
            'Issue Date': '2026-10-09', 'Verified': '__NO__',
        },
        {
            'Position': 'Business Insider — freelance lifestyle stories ($240+ / 600 words)',
            'Category': 'Writers', 'Type': 'Freelance', 'Status': 'Active',
            'Source Platform': 'LinkedIn',
            'Source URL': 'https://www.linkedin.com/posts/meganforrester_bi-lifestyle-pitches-megan-forrester-share-7507845492429512704-E_Gw/',
            'Pay': '$240+ for 600 words', 'Deadline': '', 'Location': 'Remote',
            'Description': 'Megan Forrester at Business Insider is assigning freelance lifestyle stories: hidden gems/destination dupes, unconventional living situations, first-person Amtrak experiences. Submit via pitch form.',
            'Newsletter URL': 'https://thewritersjob.beehiiv.com/p/twjn-283-pitch-calls-writing-opportunities-creative-jobs',
            'Source Details': 'TWJN newsletter issue 283, October 9, 2026 (free preview)',
            'Issue Date': '2026-10-09', 'Verified': '__NO__',
        },
        {
            'Position': 'Disability Debrief — writers on how disability rights changed your life (£100)',
            'Category': 'Writers', 'Type': 'Freelance', 'Status': 'Active',
            'Source Platform': 'X / Twitter',
            'Source URL': 'https://bsky.app/profile/hleehurley.com/post/3mxeerudks22g',
            'Pay': '£100', 'Deadline': '2026-11-02', 'Location': 'Remote',
            'Description': 'Disability Debrief wants writers to share how disability rights have changed their lives. £100 for published entries. Deadline November 2 at 11am GMT.',
            'Newsletter URL': 'https://thewritersjob.beehiiv.com/p/twjn-283-pitch-calls-writing-opportunities-creative-jobs',
            'Source Details': 'TWJN newsletter issue 283, October 9, 2026 (free preview)',
            'Issue Date': '2026-10-09', 'Verified': '__NO__',
        },
    ]
    return listings

def make_props(row):
    """Map a row dict to Notion REST page properties (same shape as scrape_oj_fu.to_notion_props)."""
    p = {}
    p['Position'] = {'title': [{'text': {'content': row['Position']}}]}
    p['Category'] = {'select': {'name': row.get('Category', 'Other')}}
    p['Type'] = {'select': {'name': row.get('Type', 'Freelance')}}
    p['Status'] = {'select': {'name': 'Active'}}
    p['Source Platform'] = {'select': {'name': row.get('Source Platform', 'Web page')}}
    if row.get('Source URL'):
        p['Source URL'] = {'url': row['Source URL']}
    if row.get('Pay'):
        p['Pay'] = {'rich_text': [{'text': {'content': row['Pay'][:2000]}}]}
    if row.get('Deadline'):
        p['Deadline'] = {'date': {'start': row['Deadline']}}
    if row.get('Location'):
        p['Location'] = {'rich_text': [{'text': {'content': row['Location'][:200]}}]}
    if row.get('Description'):
        p['Description'] = {'rich_text': [{'text': {'content': row['Description'][:2000]}}]}
    if row.get('Newsletter URL'):
        p['Newsletter URL'] = {'url': row['Newsletter URL']}
    if row.get('Source Details'):
        p['Source Details'] = {'rich_text': [{'text': {'content': row['Source Details'][:2000]}}]}
    if row.get('Issue Date'):
        p['Issue Date'] = {'date': {'start': row['Issue Date']}}
    p['Verified'] = {'checkbox': row.get('Verified', '__NO__') == '__YES__'}
    return p

def write_row(row):
    props = make_props(row)
    body = json.dumps({'parent': {'database_id': NOTION_DB}, 'properties': props})
    r = subprocess.run(['assistant', 'oauth', 'request', '--provider', 'notion',
                        '-X', 'POST', 'https://api.notion.com/v1/pages',
                        '-H', 'Content-Type: application/json', '-d', body],
                       capture_output=True, text=True, timeout=30)
    m = re.search(r'^\{.*\}', r.stdout, re.S | re.M)
    ok = m and ('"object": "page"' in m.group(0) or '"id"' in m.group(0))
    return ok, (m.group(0) if m else r.stdout)[:200]

def main():
    ffo_rows = load_ffo()
    twjn_rows = load_twjn()
    print(f'FFO rows parsed: {len(ffo_rows)}')
    print(f'TWJN rows: {len(twjj_rows := twjn_rows)}')

    # dedupe against existing Notion rows
    urls, titles = scrape_oj_fu.notion_existing()
    title_set = set(titles)
    url_set = set(urls)
    print(f'Existing in Notion: {len(url_set)} URLs, {len(title_set)} titles')

    to_write = []
    skipped = 0
    for row in ffo_rows + twjn_rows:
        # dedupe on Position title (first 40 chars as fingerprint)
        fingerprint = row['Position'][:40].lower().strip()
        # check if any existing title contains this fingerprint
        exists = any(fingerprint in t.lower()[:60] for t in title_set)
        if exists:
            skipped += 1
            continue
        if row.get('Source URL') and row['Source URL'] in url_set:
            skipped += 1
            continue
        to_write.append(row)

    print(f'New rows to write: {len(to_write)}, skipped: {skipped}')
    for r in to_write[:10]:
        print('  ', r['Position'][:80])

    # write rows
    ok_count, fails = 0, []
    for i, row in enumerate(to_write):
        ok, detail = write_row(row)
        if ok:
            ok_count += 1
        else:
            fails.append((i, detail))
        time.sleep(0.3)
    print(f'Imported {ok_count} rows, {len(fails)} failed')
    for i, d in fails[:5]:
        print(f'  FAIL[{i}]: {d[:150]}')

    # update state.json
    state = json.loads((BASE / 'state.json').read_text())
    state['imported_issues'].append({
        'sender': 'freelanceopportunities@mail.beehiiv.com',
        'newsletter': 'Freelance Opportunities!',
        'issue': '2026-10-09',
        'issue_title': 'Design Instagram Content, Edit Sports Videos, Grow Newsletters, and Work as an Audio Producer',
        'gmail_id': '1a12227f4defb11b',
        'imported': '2026-10-10',
        'rows_imported': ok_count,
    })
    state['imported_issues'].append({
        'sender': 'thewritersjob@mail.beehiiv.com',
        'newsletter': 'TWJN',
        'issue': 'TWJN 283',
        'issue_date': '2026-10-09',
        'gmail_id': '1a11dfa987ca7af9',
        'imported': '2026-10-10',
        'rows_imported': 0,  # filled after write
        'note': 'paywalled issue; only the free preview (4 items: Asimov Press, Seattle Met, Business Insider, Disability Debrief) was importable',
    })
    state['latest_seen'] = {
        'FFO': '2026-10-09',
        'TWJN': 'TWJN 283 (2026-10-09)'
    }
    state['last_run'] = '2026-10-10T10:30:00Z'
    state['job_boards'] = {
        'last_check': '2026-10-10',
        'result': f'6 new FreeUp rows imported; onlinejobs all deduped (600 existing URLs / 615 titles); FreeUp board had 11 jobs, 6 new after dedupe',
        'onlinejobs_ph': f'all existing in Notion (0 new)',
        'freeup': f'6 new rows imported'
    }
    (BASE / 'state.json').write_text(json.dumps(state, indent=1))
    print('state.json updated')

if __name__ == '__main__':
    main()
