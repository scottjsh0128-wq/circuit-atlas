import unittest,tempfile
from pathlib import Path
from simulation_metrics import parse_transient,summarize
TEXT='HEADER\nTRACE\n"out" "V"\nVALUE\n"time" 0\n"out" 0\n"time" 1\n"out" 2\n"time" 3\n"out" 2\nEND\n'
class WaveformTests(unittest.TestCase):
 def test_time_weighted_metrics(self):
  with tempfile.TemporaryDirectory() as d:
   result=summarize(TEXT,Path(d)/'wave.csv');self.assertAlmostEqual(result['metrics'][0]['time_weighted_mean'],5/3);self.assertEqual(result['metrics'][0]['peak_to_peak'],2);self.assertEqual(result['spec_verdict'],'not_evaluated')
 def test_truncated(self):
  with self.assertRaises(ValueError):parse_transient(TEXT.replace('END\n',''))
 def test_wrong_order(self):
  with self.assertRaises(ValueError):parse_transient(TEXT.replace('"out" 0','"wrong" 0'))
 def test_nonmonotonic(self):
  with self.assertRaises(ValueError):parse_transient(TEXT.replace('"time" 3','"time" 1'))
 def test_nonfinite(self):
  with self.assertRaises(ValueError):parse_transient(TEXT.replace('"out" 0','"out" 1e999'))
if __name__=='__main__':unittest.main()
