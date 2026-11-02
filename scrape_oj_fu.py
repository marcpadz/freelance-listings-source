#!/usr/bin/env python3
"""Scrape onlinejobs.ph + FreeUp job board for the daily 10am freelance-listings pipeline.

Scope: AI, automation, web design, content, sales, marketing, social media.
- onlinejobs.ph: curl login (vault creds) -> keyword searches -> parse cards.
- FreeUp: ego-browser session (task space 'freeup') -> in-page fetch of\n  timeclock.freeeup.com/project/boardv2 -> parse tickets.

Usage:
  python3 scrape_oj_fu.py              # scrape + filter + dedupe, write candidates.json
  python3 scrape_oj_fu.py --import     # also write new rows into Notion via REST
  python3 scrape_oj_fu.py --max N      # cap imported rows (testing)
"""
import json, re, sys, subprocess, time, html as htmllib
from pathlib import Path

BASE = Path('/Users/marcadrian/.local/share/vellum/assistants/vellum-faint-frog-0tgk4j/.vellum/workspace/scratch/freelance-list')
STATE = BASE / 'oj_fu_state.json'
CANDIDATES = BASE / 'oj_fu_candidates.json'
NOTION_DB = '3eaa198a-6ad6-8130-992f-dc88084d1f11'
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36'
KEYWORDS = ['ai', 'automation', 'web design', 'content', 'sales', 'marketing', 'social media']

# scope categories, checked in order (first match wins)
CATS = [
    ('AI', r'\bai\b|artificial intelligence|machine learning|\bllm\b|chatgpt|\bgpt\b|prompt engineer|ai video|ai content'),
    ('Automation', r'automat|zapier|make\.com|n8n|workflow|gohighlevel|\bghl\b|crm setup|no[- ]?code'),
    ('Web Design', r'web design|web developer|web develop|wordpress|webflow|front[- ]?end|ui/?ux|landing page|website'),
    ('Social Media', r'social media|instagram|tiktok|youtube|facebook (ads|marketer|page)|community manage|content for social'),
    ('Marketing', r'market(ing|er)|\bseo\b|\bads?\b|ppc|media buy|email marketing|campaign|growth|brand|copywrit'),
    ('Content', r'content|copywrit|\bblog\b|writ(er|ing)|editor|subtitl|caption'),
    ('Sales', r'\bsales\b|lead gen|lead generation|cold call|appointment set|business development|outreach'),
]
STRONG = re.compile('|'.join('(?:%s)' % p for _, p in CATS), re.I)

def categorize(title, desc, tags=''):
    text = f"{title} {' '.join(tags)} {desc[:350]}"
    for name, pat in CATS:
        if re.search(pat, text, re.I):
            return name
    return None

def strip_html(s):
    s = re.sub(r'<br\s*/?>', '\n', s or '', flags=re.I)
    s = re.sub(r'</(p|li|h\d|div)>', '\n', s, flags=re.I)
    s = re.sub(r'<li[^>]*>', '- ', s, flags=re.I)
    s = re.sub(r'<[^>]+>', '', s)
    s = htmllib.unescape(s)
    s = re.sub(r'\n{3,}', '\n\n', s)
    return s.strip()

def curl(url, extra=None, jar=None, out=None):
    cmd = ['curl', '-s', '-m', '40', url, '-H', f'User-Agent: {UA}', '--compressed']
    if jar: cmd += ['-b', jar, '-c', jar]
    if extra: cmd += extra
    if out: cmd += ['-o', out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.stdout if not out else None

# ---------- onlinejobs.ph ----------
def oj_login():
    """Login via vault creds; returns cookie jar path or None."""
    def reveal(field):
        r = subprocess.run(['assistant', 'credentials', 'reveal', '--service', 'onlinejobs.ph', '--field', field],
                           capture_output=True, text=True)
        return r.stdout.strip()
    user, pw = reveal('username'), reveal('password')
    if not user or not pw:
        print('OJ: no vault creds'); return None
    jar = '/tmp/oj.jar'
    curl('https://www.onlinejobs.ph/jobseekers/login', jar=jar, out='/tmp/oj_login.html')
    html = open('/tmp/oj_login.html').read()
    m = re.search(r'name="csrf-token" content="([^"]+)"', html)
    if not m: print('OJ: no csrf'); return None
    tok = m.group(1)
    code = subprocess.run(['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', '-m', '40',
        'https://www.onlinejobs.ph/authenticate', '-b', jar, '-c', jar,
        '-H', f'User-Agent: {UA}',
        '-H', 'Referer: https://www.onlinejobs.ph/jobseekers/login',
        '-H', 'Origin: https://www.onlinejobs.ph',
        '--data-urlencode', f'csrf-token={tok}',
        '--data-urlencode', f'info[email]={user}',
        '--data-urlencode', f'info[password]={pw}'], capture_output=True, text=True).stdout.strip()
    ok = code == '303'
    print(f'OJ: login POST -> {code} {"ok" if ok else "FAILED"}')
    return jar if ok else None

def oj_search(keyword, jar):
    url = f'https://www.onlinejobs.ph/jobseekers/jobsearch?jobkeyword={subprocess.list2cmdline([keyword])}'
    import urllib.parse
    url = f'https://www.onlinejobs.ph/jobseekers/jobsearch?jobkeyword={urllib.parse.quote(keyword)}'
    curl(url, jar=jar, out='/tmp/oj_s.html')
    raw = open('/tmp/oj_s.html').read()
    rows = []
    blocks = re.split(r'<!-- Start -->', raw)[1:]
    for b in blocks:
        mu = re.search(r'href="/jobseekers/job/([^"]+)"', b)
        if not mu: continue
        slug = mu.group(1)
        mt = re.search(r'<h4 class="fs-16 fw-700">(.*?)</h4>', b, re.S)
        if not mt: continue
        t = mt.group(1)
        typ = ''
        mb = re.search(r'<span class="badge[^"]*">([^<]+)</span>', t)
        if mb: typ = mb.group(1).strip()
        t_clean = re.sub(r'<span class="badge[^"]*">[^<]*</span>', '', t)
        title = re.sub(r'\s+', ' ', htmllib.unescape(re.sub(r'<[^>]+>', ' ', t_clean))).strip()
        mp2 = re.search(r'<dd class="col">(.*?)</dd>', b, re.S)
        pay = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', mp2.group(1))).strip() if mp2 else ''
        mp = re.search(r'<em>Posted on ([\d\-]+ \d+:\d+:\d+)</em>', b)
        posted = mp.group(1) if mp else ''
        md = re.search(r'<div class="desc[^"]*">(.*?)(?=<div class="job-tag"|\Z)', b, re.S)
        desc = strip_html(md.group(1)) if md else ''
        desc = re.sub(r'See More$', '', desc).strip()
        tags = re.findall(r"job-tag\">.*?</a>(.*?)</div>", b, re.S)
        tag_list = [htmllib.unescape(x.strip()) for x in re.findall(r'class=\'badge\'>([^<]+)</a>', b)]
        rows.append({'id': f'oj:{slug}', 'title': title, 'type': typ, 'posted': posted[:10],
                     'desc': desc, 'tags': tag_list, 'pay': pay,
                     'url': f'https://www.onlinejobs.ph/jobseekers/job/{slug}'})
    return rows

# ---------- FreeUp (ego-browser bridge, Marc's Oct 28/29 standing directive) ----------
# Old raw-CDP path (port probing, websocket Runtime.evaluate, Network.getCookies,
# assistant-browser navigate/click fallbacks) retired. One ego-browser task space
# named "freeup", resumed by name; the board fetch runs as an in-page page.fetch
# so the session cookies ride along automatically (same pattern as openedtabs/push.py).
EGO = 'ego-browser'
FU_SPACE = 'freeup'
FU_BOARD = 'https://timeclock.freeeup.com/project/boardv2'
FU_TICKETS_JS = r"""
let url = await page.url();
if (url.includes('/login')) {
  // session dead: FreeUp's login form may be pre-filled by the browser profile.
  // Click the login button in-page and see if it takes; otherwise report the wall.
  try {
    const filled = await page.evaluate(() =>
      [...document.querySelectorAll('input')].filter(i => i.value && i.type !== 'hidden').length);
    if (filled > 0) {
      await page.evaluate(() => {
        const el = [...document.querySelectorAll('button, input[type=submit], a')]
          .find(e => /log\s?in/i.test(e.textContent || e.value || ''));
        if (el) el.click();
      });
      await page.waitForLoadState();
      await new Promise(r => setTimeout(r, 6000));
      url = await page.url();
    }
  } catch (e) {}
}
let out = { url };
if (!url.includes('/login')) {
  const resp = await page.fetch('https://timeclock.freeeup.com/project/boardv2?page=1&page_size=100');
  let data = null;
  try { data = JSON.parse(resp.body); } catch (e) {}
  out = { url, status: resp.status, tickets: (data && data.tickets) ? data.tickets : null };
}
console.log('RESULT:' + JSON.stringify(out));
"""

def _run_ego(js_body, timeout=150):
    """Run js in the FreeUp ego-browser task space (mirrors openedtabs/push.py).
    Returns the value on the RESULT: line (console.log lands on stderr)."""
    import tempfile, os
    with tempfile.NamedTemporaryFile(mode='w', suffix='.mjs', prefix='ego-freeup-',
                                     delete=False, encoding='utf-8') as fh:
        fh.write('const task = await taskSpace(%r);\n' % FU_SPACE)
        fh.write("const page = task.page('p1');\n")
        fh.write('const _u = await page.url();\n')
        fh.write("if (!_u.includes('freeeup.com')) {\n")
        fh.write('  await page.goto(%r);\n  await page.waitForLoadState();\n}\n' % FU_BOARD)
        fh.write(js_body)
        fh.write('\nawait task.finish({ keep: [] });\n')
        path = fh.name
    try:
        r = subprocess.run([EGO, 'nodejs', '-e', "await import('file://" + path + "')"],
                           capture_output=True, text=True, timeout=timeout)
    finally:
        os.unlink(path)
    combined = ((r.stderr or '') + '\n' + (r.stdout or ''))
    if r.returncode != 0:
        raise RuntimeError('ego rc=%d: %s' % (r.returncode, combined[:300]))
    for line in reversed(combined.splitlines()):
        if line.strip().startswith('RESULT:'):
            return line.strip()[len('RESULT:'):]
    raise RuntimeError('no RESULT line: ' + combined[:300])

def fu_fetch_tickets():
    """Pull FreeUp board tickets via the ego-browser session. Returns list or None."""
    try:
        raw = _run_ego(FU_TICKETS_JS)
    except Exception as e:
        print('FU: ego failed:', str(e)[:200]); return None
    try:
        d = json.loads(raw)
    except Exception:
        print('FU: bad result', raw[:120]); return None
    if '/login' in (d.get('url') or '') or not d.get('tickets'):
        print('FU: no session (landed on %s)' % (d.get('url') or '?')[:80]); return None
    return d['tickets']

# ---------- main ----------
def scope_filter(rows):
    kept, dropped = [], 0
    for r in rows:
        cat = categorize(r['title'], r.get('desc', ''), ' '.join(r.get('tags', [])))
        if cat:
            r['category'] = cat; kept.append(r)
        else: dropped += 1
    return kept, dropped

def notion_existing():
    """All existing Source URLs + Positions from the Notion DB (paginated)."""
    urls, titles = set(), set()
    cursor = None
    while True:
        body = {'page_size': 100}
        if cursor: body['start_cursor'] = cursor
        r = subprocess.run(['assistant', 'oauth', 'request', '--provider', 'notion',
                            '-X', 'POST', f'https://api.notion.com/v1/databases/{NOTION_DB}/query',
                            '-H', 'Content-Type: application/json', '-d', json.dumps(body)],
                           capture_output=True, text=True)
        m = re.search(r'^\{.*\}', r.stdout, re.S | re.M)
        if not m: print('NOTION query failed:', r.stdout[:200], r.stderr[:200]); break
        j = json.loads(m.group(0))
        if 'results' not in j: print('NOTION err:', str(j)[:200]); break
        for row in j['results']:
            props = row.get('properties', {})
            u = props.get('Source URL', {}).get('url')
            if u: urls.add(u.rstrip('/').lower())
            ti = props.get('Position', {}).get('title', [])
            if ti and ti[0].get('plain_text'): titles.add(ti[0]['plain_text'].strip().lower())
        if not j.get('has_more'): break
        cursor = j.get('next_cursor')
    return urls, titles

def dedupe(rows, urls, titles):
    seen, kept = set(), []
    for r in rows:
        u = r['url'].rstrip('/').lower()
        if u in urls or r['id'] in seen: continue
        if r['title'].strip().lower() in titles: continue
        seen.add(r['id']); kept.append(r)
    return kept

VALID_TYPES = {'Freelance', 'Part-time', 'Full-time', 'Hourly', 'Fellowship', 'Grant', 'Other'}

def map_type(t):
    t = (t or '').strip()
    if t in VALID_TYPES: return t
    tl = t.lower()
    if 'full' in tl: return 'Full-time'
    if 'part' in tl: return 'Part-time'
    if 'hour' in tl: return 'Hourly'
    if 'gig' in tl or 'any' in tl or 'fix' in tl or 'freelance' in tl: return 'Freelance'
    return 'Other'

def to_notion_props(r):
    return {
        'Position': {'title': [{'text': {'content': r['title']}}]},
        'Category': {'select': {'name': r['category']}},
        'Type': {'select': {'name': map_type(r.get('type'))}},
        'Status': {'select': {'name': 'Active'}},
        'Source Platform': {'select': {'name': 'OnlineJobs.ph' if r['id'].startswith('oj:') else 'FreeUp'}},
        'Source URL': {'url': r['url']},
        'Pay': {'rich_text': [{'text': {'content': (r.get('pay') or '')[:2000]}}]},
        'Location': {'rich_text': [{'text': {'content': (r.get('loc') or 'Remote')[:2000]}}]},
        'Description': {'rich_text': [{'text': {'content': r.get('desc', '')[:2000]}}]},
        'Source Details': {'rich_text': [{'text': {'content': ('onlinejobs.ph search' if r['id'].startswith('oj:') else 'FreeUp job board')[:2000]}}]},
        'Issue Date': {'date': {'start': r['posted']}} if r.get('posted') else None,
        'Verified': {'checkbox': True},
    }

def notion_import(rows, max_n=None):
    ok, fail = 0, []
    for r in rows[:max_n] if max_n else rows:
        props = {k: v for k, v in to_notion_props(r).items() if v is not None}
        body = json.dumps({'parent': {'database_id': NOTION_DB}, 'properties': props})
        p = subprocess.run(['assistant', 'oauth', 'request', '--provider', 'notion', '-X', 'POST',
                            'https://api.notion.com/v1/pages', '-H', 'Content-Type: application/json',
                            '-d', body], capture_output=True, text=True)
        m = re.search(r'^\{.*\}', p.stdout, re.S | re.M)
        good = m and ('"id"' in m.group(0) and '"object": "page"' in m.group(0))
        if good: ok += 1
        else:
            fail.append((r['id'], (m.group(0) if m else p.stdout)[:150]))
        time.sleep(0.4)
    return ok, fail

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--import', dest='do_import', action='store_true')
    ap.add_argument('--max', type=int, default=None)
    ap.add_argument('--skip-oj', action='store_true')
    ap.add_argument('--skip-fu', action='store_true')
    args = ap.parse_args()
    BASE.mkdir(parents=True, exist_ok=True)

    all_rows = []
    if not args.skip_oj:
        jar = oj_login()
        seen_slugs = set()
        for kw in KEYWORDS:
            rows = oj_search(kw, jar)
            new = [r for r in rows if r['id'] not in seen_slugs]
            for r in new: r['_kw'] = kw
            seen_slugs.update(r['id'] for r in rows)
            all_rows.extend(new)
            print(f'OJ keyword {kw!r}: {len(rows)} cards, {len(new)} new-unique')
            time.sleep(1.5)
    if not args.skip_fu:
        tickets = fu_fetch_tickets()
        if tickets:
            rows = fu_rows(tickets)
            print(f'FU: {len(tickets)} tickets -> {len(rows)} rows')
            all_rows.extend(rows)
        else:
            print('FU: SKIPPED (no session)')

    kept, dropped = scope_filter(all_rows)
    print(f'scope filter: kept {len(kept)}, dropped {dropped}')
    urls, titles = notion_existing()
    print(f'notion existing: {len(urls)} urls, {len(titles)} titles')
    fresh = dedupe(kept, urls, titles)
    print(f'after dedupe: {len(fresh)} new rows')

    CANDIDATES.write_text(json.dumps(fresh, indent=1))
    if args.do_import and fresh:
        ok, fail = notion_import(fresh, args.max)
        print(f'imported {ok} rows, {len(fail)} failed')
        for fid, err in fail[:5]: print(' FAIL', fid, err)
        # record state
        st = json.loads(STATE.read_text()) if STATE.exists() else {'imported_ids': []}
        for r in fresh[:args.max] if args.max else fresh:
            if r['id'] not in st['imported_ids']: st['imported_ids'].append(r['id'])
        st['last_run'] = time.strftime('%Y-%m-%dT%H:%M:%S')
        STATE.write_text(json.dumps(st, indent=1))
    print('candidates file:', CANDIDATES)

if __name__ == '__main__':
    main()
