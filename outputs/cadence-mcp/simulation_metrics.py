"""Strict reader for Spectre real-valued, single-sweep transient PSF ASCII."""
import math
import re
import csv

def parse_transient(text):
    if '\nVALUE\n' not in text or '\nTRACE\n' not in text:
        raise ValueError('Missing PSF TRACE or VALUE section')
    header, values = text.split('\nVALUE\n', 1)
    trace = header.split('\nTRACE\n', 1)[1]
    signals = []
    for line in trace.strip().splitlines():
        match = re.fullmatch(r'"([^"\\]+)" "(V|I)"', line.strip())
        if not match:
            raise ValueError('Unsupported trace type; expected scalar voltage/current')
        signals.append((match[1], match[2]))
    names = ['time'] + [s[0] for s in signals]
    if len(set(names)) != len(names):
        raise ValueError('Duplicate signal')
    rows = []; row = []; ended = False
    for line in values.splitlines():
        line = line.strip()
        if line == 'END':
            ended = True
            break
        if not line:
            continue
        match = re.fullmatch(r'"([^"\\]+)" ([+\-0-9.eE]+)', line)
        if not match or match[1] != names[len(row)]:
            raise ValueError('Unsupported or incomplete sample layout')
        value = float(match[2])
        if not math.isfinite(value):
            raise ValueError('Nonfinite waveform value')
        row.append(value)
        if len(row) == len(names):
            if rows and row[0] <= rows[-1][0]:
                raise ValueError('Time must increase strictly')
            rows.append(row); row = []
    if not ended or row or len(rows) < 2:
        raise ValueError('Incomplete waveform')
    return names, signals, rows

def summarize(text, csv_path):
    names, signals, rows = parse_transient(text)
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f); writer.writerow(['time_s'] + [n+'_'+u for n,u in signals]); writer.writerows(rows)
    duration = rows[-1][0]-rows[0][0]
    metrics = []
    for index,(name,unit) in enumerate(signals,1):
        values = [r[index] for r in rows]
        mean = sum((rows[k][0]-rows[k-1][0])*(values[k]+values[k-1])/2 for k in range(1,len(rows)))/duration
        metrics.append({'signal':name,'unit':unit,'min':min(values),'max':max(values),'peak_to_peak':max(values)-min(values),'time_weighted_mean':mean})
    return {'schema':'circuit-atlas-simulation/1','analysis':'tran','sample_count':len(rows),
      'time_start_s':rows[0][0],'time_end_s':rows[-1][0], 'metrics':metrics,
      'measurement_window':'entire transient including startup','waveform_csv':str(csv_path),
      'spec_verdict':'not_evaluated','limitations':['No target or measurement window configured','No SNDR, GBW, SR or PM inferred from waveform ranges']}
