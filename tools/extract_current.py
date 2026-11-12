"""Extract a saved official Hamburg Gesamtausgabe JSON response, offline."""
import argparse
import json
from pathlib import Path
from parse_current import parse, verify_official
from parse_tables import enhance, verify_tables

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('document_id')
    args=parser.parse_args()
    raw=args.source.read_bytes()
    act,facts=parse(raw,args.document_id)
    if act:
        enhance(raw,act)
        verify_official(raw,act)
        verify_tables(raw,act)
    print(json.dumps({'act':act,'source_facts':facts},ensure_ascii=False,indent=1))

if __name__=='__main__':
    main()
