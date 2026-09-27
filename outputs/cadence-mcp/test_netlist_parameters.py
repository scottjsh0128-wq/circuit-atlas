import unittest
from netlist_parameters import public_catalog,apply_overrides
NET='V8 (Vp 0) vsource type=sine ampl=250m \\\n freq=1K\nNM1 (d g s b) model w=(3.2u) l=130n m=(1)*(1)\ntran tran stop=1m write="spectre.ic"\n'
class ParameterTests(unittest.TestCase):
 def test_catalog(self):
  p={x['key']:x['value'] for x in public_catalog(NET)}
  self.assertEqual(p['V8.freq'],'1K');self.assertEqual(p['NM1.w'],'(3.2u)');self.assertNotIn('NM1.m',p);self.assertNotIn('tran.write',p)
 def test_changes_preserve_other_values(self):
  modified,changes=apply_overrides(NET,{'V8.freq':'2k','NM1.w':'4u'})
  self.assertIn('freq=2k',modified);self.assertIn('w=4u l=130n',modified);self.assertIn('ampl=250m',modified);self.assertEqual(len(changes),2)
 def test_reject_code_and_paths(self):
  for value in ['1k\n','1k;run()','(system("x"))','foo','1k stop=1','NaN']:
   with self.assertRaises(ValueError):apply_overrides(NET,{'V8.freq':value})
  with self.assertRaises(ValueError):apply_overrides(NET,{'tran.write':'1'})
 def test_duplicate_keys_rejected(self):
  with self.assertRaises(ValueError):apply_overrides(NET+'V8 (x 0) vsource freq=2k\n',{'V8.freq':'1k'})
if __name__=='__main__':unittest.main()
