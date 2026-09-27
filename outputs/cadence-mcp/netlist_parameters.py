"""Numeric literal overrides for existing Spectre statements; Python 2.6 compatible."""
import re
NUMBER=r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?(?:[TGMKkmunpfa](?:s|Hz|V|A|F|Ohm)?|s|Hz|V|A|F|Ohm)?'
LITERAL=re.compile(r'^(?:'+NUMBER+r'|\('+NUMBER+r'\))\Z')
ASSIGN=re.compile(r'(?<!\S)([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([^\s]+)')

def catalog(text):
    logical=re.sub(r'\\\r?\n[ \t]*',' ',text)
    entries=[];seen={};offset=0
    for line in logical.splitlines(True):
        stripped=line.strip()
        if not stripped or stripped.startswith('//'):
            offset+=len(line);continue
        label=stripped.split()[0]
        if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$',label):
            offset+=len(line);continue
        code=line.split('//',1)[0]
        for match in ASSIGN.finditer(code):
            if LITERAL.match(match.group(2)):
                key=label+'.'+match.group(1)
                entries.append({'key':key,'statement':label,'parameter':match.group(1),'value':match.group(2),'start':offset+match.start(2),'end':offset+match.end(2)})
                seen[key]=seen.get(key,0)+1
        offset+=len(line)
    return logical,[e for e in entries if seen[e['key']]==1]

def public_catalog(text):
    _,entries=catalog(text)
    return [dict((k,v) for k,v in e.items() if k not in ('start','end')) for e in entries]

def apply_overrides(text,overrides):
    if not isinstance(overrides,dict) or len(overrides)>100:raise ValueError('Use at most 100 numeric overrides')
    logical,entries=catalog(text);lookup=dict((e['key'],e) for e in entries);changes=[]
    for key,value in overrides.items():
        if key not in lookup:raise ValueError('Unknown or ambiguous parameter: '+key)
        if not isinstance(value,str):
            try:value=value.encode('ascii')
            except (AttributeError,UnicodeError):raise ValueError('Parameter value must be a numeric string')
        if len(value)>40 or not LITERAL.match(value):raise ValueError('Numeric literal required for '+key)
        entry=lookup[key];changes.append({'key':key,'before':entry['value'],'after':value})
    for entry in sorted([lookup[k] for k in overrides],key=lambda e:e['start'],reverse=True):
        value=next(c['after'] for c in changes if c['key']==entry['key'])
        logical=logical[:entry['start']]+value+logical[entry['end']:]
    return logical,sorted(changes,key=lambda c:c['key'])
