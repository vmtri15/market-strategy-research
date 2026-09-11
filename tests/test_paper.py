import tempfile
import unittest
from pathlib import Path
from src.paper.engine import initialize,set_paused,process_day,connect,SYMBOLS


class PaperTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=Path(self.tmp.name)/'paper.db'
        source=Path(self.tmp.name)/'source';source.write_bytes(b'frozen test model')
        initialize(db=self.db,source=source,model_path=Path(self.tmp.name)/'frozen')
        set_paused(False,self.db)
        self.bars={s:{'open':100.,'close':100.} for s in SYMBOLS}
        self.signals={s:(1,.8) for s in SYMBOLS}
    def tearDown(self):
        self.tmp.cleanup()
    def test_next_session_idempotency_and_limits(self):
        process_day(self.bars,self.signals,'2026-09-08','2026-09-04',self.db)
        with connect(self.db) as c:
            self.assertEqual(c.execute("select count(*) from orders where status='filled'").fetchone()[0],0)
        process_day(self.bars,self.signals,'2026-09-09','2026-09-08',self.db)
        self.assertEqual(process_day(self.bars,self.signals,'2026-09-09','2026-09-08',self.db),'duplicate')
        with connect(self.db) as c:
            fills=c.execute("select * from orders where status='filled'").fetchall()
            self.assertEqual(len(fills),3)
            for order in fills:self.assertAlmostEqual(order['quantity']*order['price']+order['fee'],3000)
            self.assertAlmostEqual(c.execute('select cash from account').fetchone()[0],1000)
    def test_invalid_inputs_are_atomic(self):
        process_day(self.bars,self.signals,'2026-09-08','2026-09-04',self.db)
        self.bars['SPY']['open']=-1
        with self.assertRaises(ValueError):process_day(self.bars,self.signals,'2026-09-09','2026-09-08',self.db)
        with connect(self.db) as c:self.assertEqual(c.execute('select last_date from account').fetchone()[0],'2026-09-08')
    def test_gap_pauses_and_cancels(self):
        process_day(self.bars,self.signals,'2026-09-08','2026-09-04',self.db)
        self.assertEqual(process_day(self.bars,self.signals,'2026-09-10','2026-09-09',self.db),'gap')
        with connect(self.db) as c:
            self.assertEqual(c.execute('select paused from account').fetchone()[0],1)
            self.assertEqual(c.execute("select count(*) from orders where status='pending'").fetchone()[0],0)
    def test_pause_prevents_execution(self):
        set_paused(True,self.db)
        self.assertEqual(process_day(self.bars,self.signals,'2026-09-08','2026-09-04',self.db),'paused')
