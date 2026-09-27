"""Parse Spectre PSF ASCII operating-point STRUCT records with source context."""
import re,json,math

def parse_op(text):
    if '\nTYPE\n' not in text or '\nVALUE\n' not in text or not text.rstrip().endswith('END'):
        raise ValueError('Incomplete operating-point PSF')
    header,body=text.split('\nTYPE\n',1);types,values=body.split('\nVALUE\n',1)
    starts=list(re.finditer(r'^"([^"\\]+)" STRUCT\(\s*$',types,re.M));definitions={}
    for i,m in enumerate(starts):
        definition=types[m.end():starts[i+1].start() if i+1<len(starts) else len(types)]
        definitions[m[1]]=re.findall(r'^"([^"\\]+)" (?:FLOAT|INT) (?:DOUBLE|BYTE|LONG)',definition,re.M)
    records=[]
    for m in re.finditer(r'^"([^"\\]+)" "([^"\\]+)" \(\n(.*?)^\)(?: PROP\(\n(.*?)^\))?',values,re.M|re.S):
        fields=definitions.get(m[2]);numbers=m[3].strip().splitlines()
        if not fields or len(fields)!=len(numbers):raise ValueError('Unknown or mismatched OP record '+m[1])
        data=dict(zip(fields,map(float,numbers)))
        if not all(math.isfinite(v) for v in data.values()):raise ValueError('Nonfinite OP value')
        model=re.search(r'^"model" "([^"]+)"',m[4] or '',re.M)
        records.append({'name':m[1],'type':m[2],'model':model[1] if model else m[2],'raw':data})
    if not records:raise ValueError('No operating-point records')
    devices=[];sources=[]
    for r in records:
        d=r['raw']
        if all(k in d for k in ('gm','vds','vdsat')):
            current=d.get('ids',d.get('id'));gds=d.get('gds')
            r.update(id=current,gm=d['gm'],gds=gds,gm_id=abs(d['gm']/current) if current is not None and abs(current)>1e-15 else None,
              gm_gds=abs(d['gm']/gds) if gds is not None and abs(gds)>1e-15 else None,
              vds=d['vds'],vdsat=d['vdsat'],margin=abs(d['vds'])-abs(d['vdsat']),region=d.get('region'))
            devices.append(r)
        elif r['type']=='vsource':sources.append(r)
    context={k:re.search(r'^"'+k+r'" (.*)$',header,re.M)[1] for k in ['AnalysisType','ParameterValue','OpPointTemp.Value'] if re.search(r'^"'+k+r'" (.*)$',header,re.M)}
    return {'devices':devices,'sources':sources,'context':context,'margin_definition':'abs(VDS)-abs(VDSAT); diagnostic, not a universal operating-region test','region_mapping':'raw PDK codes; no automatic role/region pass verdict'}
