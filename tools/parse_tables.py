"""Preserve source text tables as inert HTML within Markdown law files."""
import copy
import re
import json
import html as html_std
from bs4 import BeautifulSoup, NavigableString, Comment
from parse_current import norm

def source_table(table):
    table=copy.deepcopy(table)
    if table.find(['img','svg','object','embed','canvas','script','style']):
        raise ValueError('nontext/active content in legal table')
    for element in [table,*table.find_all(True)]:
        element.attrs={k:v for k,v in element.attrs.items() if k in {'rowspan','colspan','scope'} and element.name in {'td','th'}}
    return str(table)

def paragraphs_with_tables(element):
    tables=[]
    blocks={'p','div','h1','h2','h3','h4','h5','h6','dt','dd','li','tr','br'}
    def visit(node):
        if isinstance(node,Comment):
            return ''
        if isinstance(node,NavigableString):
            return str(node)
        if node.name=='table':
            token=f'Q6TABLEPLACEHOLDER{len(tables)}ENDTOKEN'
            tables.append((token,source_table(node)))
            return '\n'+token+'\n'
        value=''.join(visit(x) for x in node.children)
        return '\n'+value+'\n' if node.name in blocks else value
    text='\n'.join(x for x in (norm(v) for v in visit(element).splitlines()) if x)+'\n'
    for token,table in tables:
        text=text.replace(token,table)
    return text

def enhance(raw,act):
    data=json.loads(raw)
    soup=BeautifulSoup(data['text'],'html.parser')
    content=soup.select_one('.docLayoutText')
    changed=[]
    for child in content.find_all(recursive=False):
        anchor=child.find('a',attrs={'name':re.compile('^'+re.escape(act['id'])+'NN[0-9]+$')},recursive=False)
        if anchor and child.find('table'):
            key='norm-'+anchor['name'].rsplit('NN',1)[-1]
            text=paragraphs_with_tables(child)
            if text!=act['versions'][0]['units'][key]['text']:
                act['versions'][0]['units'][key]['text']=text
                changed.append(key)
    return changed

def table_signature(table):
    return [[(cell.tag.lower(),cell.get('rowspan','1'),cell.get('colspan','1'),norm(''.join(cell.itertext())))
             for cell in row if isinstance(cell.tag,str) and cell.tag.lower() in {'td','th'}]
            for row in table.iter('tr')]

def output_dom(text):
    from lxml import html
    chunks=[]
    cursor=0
    depth=0
    for match in re.finditer(r'<table\b|</table>',text):
        if match.group().startswith('<table'):
            if depth==0:
                chunks.append(html_std.escape(text[cursor:match.start()]))
                begin=match.start()
                depth=0
            depth+=1
        else:
            depth-=1
            if depth==0:
                chunks.append(text[begin:match.end()])
                cursor=match.end()
    chunks.append(html_std.escape(text[cursor:]))
    encoded=''.join(chunks)
    return html.fromstring('<div>'+encoded+'</div>')

def verify_tables(raw,act):
    from lxml import html
    data=json.loads(raw)
    root=html.fromstring(data['text'])
    count=0
    for node in root.xpath('//a[@name]'):
        name=node.get('name','')
        if not re.fullmatch(re.escape(act['id'])+r'NN[0-9]+',name):
            continue
        source=node.getparent()
        key='norm-'+name.rsplit('NN',1)[-1]
        output=output_dom(act['versions'][0]['units'][key]['text'])
        src=source.xpath('.//table')
        out=output.xpath('.//table')
        if len(src)!=len(out) or [table_signature(t) for t in src]!=[table_signature(t) for t in out]:
            raise ValueError('independent source table rows/cells/merged cells mismatch '+act['id']+' '+key+f'; table counts {len(src)}/{len(out)}')
        count+=len(src)
    return count
