#!/usr/bin/env python3
"""Keep KiCad 10 unrouted placement studies readable by pinned atopile 0.15.9.

This is deliberately narrow: no tracks, vias, filled copper or non-default via
manufacturing settings. Numeric net IDs come from the original circuit capture,
and an independent graph comparison rejects any electrical change.
"""
import argparse
from pathlib import Path
import re
import tempfile

from kicad_sexpr import children, one, parse, dumps
from generate_schematics import board_graph


def normalize(source, reference):
    parsed=parse(source)
    original=parse(reference.read_text())
    if str(one(parsed,'version')[1])!='20260206':
        raise ValueError('Only the reviewed KiCad 10 placement format is supported')
    if any(children(parsed,tag) for tag in ('segment','arc','via')):
        raise ValueError('Refusing to convert routed copper')
    for zone in children(parsed,'zone'):
        if not children(zone,'keepout') or children(zone,'filled_polygon'):
            raise ValueError('Only unfilled rule areas are supported')
    nets={str(n[2]):str(n[1]) for n in children(original,'net')}
    if len(nets)!=len(children(original,'net')):
        raise ValueError('Reference net names must be unique')
    if children(parsed,'net'):
        raise ValueError('Expected KiCad 10 name-only net format')
    def net(m):
        name=parse(m[0])[1]
        if name not in nets:raise ValueError('New net appeared during placement: '+name)
        return '(net '+nets[name]+' '+dumps(name)+')'
    source=re.sub(r'\(net "(?:\\.|[^"\\])*"\)',net,source)
    setup=one(parsed,'setup')
    tenting=one(setup,'tenting')
    if {str(n[0]):str(n[1]) for n in tenting[1:]}!={'front':'yes','back':'yes'}:
        raise ValueError('Non-default via tenting requires a separate process review')
    source=re.sub(r'\(tenting\s+\(front yes\)\s+\(back yes\)\s*\)',
                  '(tenting front back)',source,count=1)
    for key in ('covering','plugging'):
        value=one(setup,key)
        if {str(n[0]):str(n[1]) for n in value[1:]}!={'front':'no','back':'no'}:
            raise ValueError('Non-default '+key+' cannot be discarded')
        source=re.sub(r'\s*\('+key+r'\s+\(front no\)\s+\(back no\)\s*\)','',source,count=1)
    for key in ('capping','filling'):
        if str(one(setup,key)[1])!='no':raise ValueError('Non-default '+key)
        source=re.sub(r'\s*\('+key+r' no\)','',source,count=1)
    source=source.replace('(version 20260206)','(version 20241229)',1)
    # KiCad 10 omits the explicit no-net fields of rule areas; the pinned
    # compiler requires them even though these areas cannot contain copper.
    source=re.sub(r'\(zone\s*\n', '(zone\n\t\t(net 0)\n\t\t(net_name "")\n',source)
    definitions='\n'.join('\t'+dumps(n) for n in children(original,'net'))
    source=source.replace('\n\t(footprint','\n'+definitions+'\n\t(footprint',1)
    with tempfile.TemporaryDirectory() as folder:
        path=Path(folder)/'normalized.kicad_pcb';path.write_text(source)
        before,after=board_graph(reference),board_graph(path)
        if before.keys()!=after.keys():raise ValueError('Circuit component set changed')
        for ref in before:
            for key in ('Datasheet','Description'):
                if key not in before[ref]['properties'] and after[ref]['properties'].get(key)=='':
                    del after[ref]['properties'][key]
            if before[ref]!=after[ref]:raise ValueError('Circuit identity or nets changed: '+ref)
    return source


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path);p.add_argument('--reference',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=normalize(a.source.read_text(),a.reference)
    a.output.write_text(result)
    print('Unrouted placement normalized; complete electrical graph unchanged:',a.output)


if __name__=='__main__':main()
