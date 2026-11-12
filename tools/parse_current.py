"""Deterministically parse juris current Gesamtausgabe HTML; no network."""
import re
import hashlib
import json
import datetime
from bs4 import BeautifulSoup, NavigableString, Comment
TODAY = '2026-11-12'

def norm(text):
    return re.sub(r'\s+', ' ', text.replace('\xa0', ' ')).strip()

def iso(day):
    return datetime.datetime.strptime(day, '%d.%m.%Y').date().isoformat()

def paragraphs(element):
    blocks = {'p','div','h1','h2','h3','h4','h5','h6','dt','dd','li','tr','br'}
    def visit(node):
        if isinstance(node, Comment):
            return ''
        if isinstance(node, NavigableString):
            return str(node)
        if node.name in {'script','style'}:
            raise ValueError('script/style inside normative content')
        value = ''.join(visit(x) for x in node.children)
        return '\n' + value + '\n' if node.name in blocks else value
    return '\n'.join(x for x in (norm(v) for v in visit(element).splitlines()) if x) + '\n'

def parse(raw, doc_id):
    data = json.loads(raw)
    if 'text' not in data or 'head' not in data:
        raise ValueError('no official text/head')
    head = BeautifulSoup(data['head'], 'html.parser')
    facts = {}
    for row in head.find_all('tr'):
        cells = row.find_all(['th','td'], recursive=False)
        if len(cells) == 2:
            facts[norm(cells[0].get_text()) .rstrip(':')] = norm(cells[1].get_text())
    kind = facts.get('Dokumenttyp', '')
    if kind not in {'Gesetz', 'Verordnung', 'Verfassung'}:
        return None, {'reason':'outside scope', 'document_type':kind, 'facts':facts}
    soup = BeautifulSoup(data['text'], 'html.parser')
    content = soup.select_one('.docLayoutText')
    title = soup.select_one('.docLayoutTitel')
    if not content or not title:
        raise ValueError('no Gesamtausgabe title or text')
    banner = content.select_one('.docLayoutMarginTopMore')
    banner_text = norm(banner.get_text()) if banner else ''
    match = re.search(r'Gesamtausgabe in der Gültigkeit vom (\d{2}\.\d{2}\.\d{4})(?: bis (\d{2}\.\d{2}\.\d{4}))?', banner_text)
    toc = content.select('.jwsinhaltsverzeichnis tr')
    dates = []
    toc_ids = []
    for row in toc:
        cells = row.find_all('td', recursive=False)
        if len(cells) >= 2:
            links = cells[0].find_all('a', attrs={'data-juris-link':True})
            if links:
                anchor = json.loads(links[0]['data-juris-link']).get('linkMeta',{}).get('anchor')
                if anchor:
                    toc_ids.append(anchor)
            dm = re.search(r'\d{2}\.\d{2}\.\d{4}', cells[1].get_text())
            if dm:
                dates.append(iso(dm.group()))
    if match:
        day = iso(match.group(1))
        end = iso(match.group(2)) if match.group(2) else None
        basis = 'Official Gesamtausgabe states: ' + banner_text
        if day > TODAY or (end and end < TODAY):
            return None, {'reason':'not in force on checked day', 'from':day, 'to':end, 'facts':facts}
    elif 'aktuellste verfügbare Fassung der Gesamtausgabe' in banner_text and dates:
        day = max(dates)
        basis = 'Latest Gültig ab date in the official current Gesamtausgabe provision table: ' + day
        end = None
    else:
        raise ValueError('no dated current Gesamtausgabe; hold rather than invent date')
    if day > TODAY or any(d > TODAY for d in dates):
        raise ValueError('future-dated provision in current Gesamtausgabe')
    if facts.get('Gültig bis') and iso(facts['Gültig bis']) < TODAY:
        return None, {'reason':'not in force on checked day','facts':facts}
    containers = []
    for child in content.find_all(recursive=False):
        anchor = child.find('a', attrs={'name':re.compile('^' + re.escape(doc_id) + 'NN[0-9]+$')}, recursive=False)
        if anchor:
            containers.append((anchor['name'], child))
    if not containers:
        raise ValueError('no anchored legal provisions')
    actual_ids = [a for a,_ in containers]
    expected_ids = [a for a in toc_ids if a != doc_id]
    if actual_ids != expected_ids:
        raise ValueError(f'legal containers differ from official table of contents: {len(actual_ids)}/{len(expected_ids)}')
    images = []
    for anchor, container in containers:
        for image in container.find_all(['img','svg','object','embed','canvas']):
            images.append({'position':anchor,'url':image.get('src') or image.get('data') or '', 'caption':image.get('alt','')})
    if images:
        return None, {'reason':'normative images deferred; live asset sync not confirmed', 'images':images, 'from':day, 'facts':facts}
    units = {'title':{'label':'Titel', 'kind':'title', 'text':paragraphs(title)}}
    for anchor, container in containers:
        key = 'norm-' + anchor.rsplit('NN',1)[-1]
        units[key] = {'label':key, 'kind':'section', 'text':paragraphs(container)}
    enacted = facts.get('Ausfertigungsdatum')
    act = {'slug':doc_id.lower(), 'id':doc_id, 'short':facts.get('Amtliche Abkürzung') or facts.get('juris-Abkürzung') or doc_id,
           'title':norm(title.get_text(' ',strip=True)), 'url':'https://www.landesrecht-hamburg.de/bsha/document/' + doc_id,
           'first_law':None, 'earlier_laws':[], 'law_kind':'regulation' if kind=='Verordnung' else 'constitution' if kind=='Verfassung' else 'act',
           'enacted':iso(enacted) if enacted and re.fullmatch(r'\d{2}\.\d{2}\.\d{4}', enacted) else None,
           'status':'in force','images':0,'images_omitted':0,
           'versions':[{'from':day,'source_url':'https://www.landesrecht-hamburg.de/perma?d=' + doc_id + '&docPart=X',
                        'sha256':hashlib.sha256(raw).hexdigest(),'units':units,'credits':{},'in_force_basis':basis,
                        'text_as_of':TODAY,'note':'Current consolidated text checked on ' + TODAY + '; earlier versions not collected.'}]}
    return act, {'reason':'parsed','facts':facts,'banner':banner_text,'from':day,'to':end,'source_images':0,
                 'unit_ids':actual_ids,'source_sha256':hashlib.sha256(raw).hexdigest()}

def verify_official(raw, act):
    """Independent lxml DOM proof against the original publisher response bytes."""
    from lxml import html, etree
    data = json.loads(raw)
    root = html.fromstring(data['text'])
    title = root.xpath('//*[contains(concat(" ", normalize-space(@class), " "), " docLayoutTitel ")]')[0]
    doc_id = act['id']
    pairs = [('title',title)]
    for node in root.xpath('//a[@name]'):
        name = node.get('name','')
        if re.fullmatch(re.escape(doc_id) + r'NN[0-9]+', name):
            pairs.append(('norm-' + name.rsplit('NN',1)[-1], node.getparent()))
    if set(k for k,_ in pairs) != set(act['versions'][0]['units']):
        raise ValueError('independent source unit set differs')
    for key, source in pairs:
        # Add only rendered block boundaries; legal words/punctuation remain source text.
        for el in source.iter():
            if isinstance(el.tag,str) and el.tag.lower() in {'p','div','h1','h2','h3','h4','h5','h6','dt','dd','li','tr','br'}:
                el.text = '\n' + (el.text or '')
                el.tail = '\n' + (el.tail or '')
        for comment in source.xpath('.//comment()'):
            comment.getparent().remove(comment)
        source_text = norm(source.text_content())
        from parse_tables import output_dom
        output=output_dom(act['versions'][0]['units'][key]['text'])
        for el in output.iter():
            if isinstance(el.tag,str) and el.tag.lower() in {'p','div','h1','h2','h3','h4','h5','h6','dt','dd','li','tr','br'}:
                el.text='\n'+(el.text or '')
                el.tail='\n'+(el.tail or '')
        output_text = norm(output.text_content())
        if source_text != output_text:
            raise ValueError('independent word-for-word mismatch: ' + key)
    # Date proof reads a different DOM and compares the banner/table with the built date.
    banners = root.xpath('//*[contains(concat(" ", normalize-space(@class), " "), " docLayoutMarginTopMore ")]')
    banner = norm(banners[0].text_content()) if banners else ''
    dm = re.search(r'Gesamtausgabe in der Gültigkeit vom (\d{2}\.\d{2}\.\d{4})',banner)
    if dm:
        expected_day = iso(dm.group(1))
    else:
        vals = root.xpath('//*[contains(concat(" ", normalize-space(@class), " "), " jwsinhaltsverzeichnis ")]//tr/td[2]')
        expected_day = max(iso(re.search(r'\d{2}\.\d{2}\.\d{4}', x.text_content()).group()) for x in vals if re.search(r'\d{2}\.\d{2}\.\d{4}', x.text_content()))
    if expected_day != act['versions'][0]['from']:
        raise ValueError('independent source date mismatch')
    return len(pairs)
