import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'cadence-mcp'))
import workbench_service as service
from operating_point import parse_op

class BackendTests(unittest.TestCase):
    def test_real_op_fields(self):
        p=Path(__file__).resolve().parents[2]/'cadence-mcp/simulation-results/06a81747cf604a25870038ded3f0267f/operating-point.psf'
        if not p.exists():self.skipTest('Local measured artifact is not packaged')
        op=parse_op(p.read_text());self.assertEqual(len(op['devices']),14)
        for d in op['devices']:
            self.assertAlmostEqual(d['margin'],abs(d['raw']['vds'])-abs(d['raw']['vdsat']))
        with self.assertRaises(ValueError):parse_op(p.read_text().removesuffix('END\n'))
    def test_durable_queue(self):
        old_db,old_worker=service.DB,service.ensure_worker
        try:
            with tempfile.TemporaryDirectory() as directory:
                service.DB=Path(directory)/'test.sqlite3';service.ensure_worker=lambda:None;service.init()
                bid=service.save_block({'project_id':'project-initial','name':'Test','kind':'custom','cell':'testbench','rails':[]})
                first=service.start_run(bid,'a'*64)
                second=service.start_run(bid,'a'*64)
                service.cancel_run(first['id'])
                service.init()
                claimed=service.claim();self.assertEqual(claimed['id'],second['id'])
                self.assertIsNone(service.claim())
                states={r['id']:r['status'] for r in service.public_state()['runs']}
                self.assertEqual(states[first['id']],'cancelled');self.assertEqual(states[second['id']],'running')
        finally:service.DB,service.ensure_worker=old_db,old_worker

if __name__=='__main__':unittest.main()
