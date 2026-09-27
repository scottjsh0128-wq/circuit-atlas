import assert from 'node:assert/strict';
import {defaults,theory,spectrum,sndr,runModel} from '../dist/spec-model.js';
import test from 'node:test';
test('thermal capacitance inverts the same noise equation',()=>{const t=theory(defaults);for(const c of t.caps){const recovered=theory({...defaults,Cs:c.C});assert.ok(Math.abs(recovered.snrThermal-c.snr)<1e-9);}assert.ok(Math.abs(t.beta-.8)<1e-12);});
test('PSD integrates to known sine power; distortion appears in SNDR',()=>{const N=16384,fs=16384,k=101,y=Float64Array.from({length:N},(_,i)=>Math.sin(2*Math.PI*k*i/N)+.01*Math.sin(2*Math.PI*2*k*i/N));const s=spectrum(y,fs);assert.ok(Math.abs(s.psd.reduce((a,b)=>a+b,0)*s.df-.50005)<1e-8);assert.ok(Math.abs(sndr(s,k,1000).sndr-40)<1e-5);assert.throws(()=>sndr(s,1000,1000));});
test('behavioral model and sweeps return finite metrics with explicit provenance',()=>{const result=runModel({...defaults,N:8192,fin:700});assert.equal(result.sweeps.length,6);assert.equal(result.amplitudes.length,21);assert.ok(Number.isFinite(result.real.sndr));assert.ok(result.source.includes('MATLAB'));assert.equal(result.conditions.PM,70);});
