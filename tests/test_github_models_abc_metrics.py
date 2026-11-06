import unittest
from github_models.abc_metrics import metrics

class TestABCMetrics(unittest.TestCase):
    def test_unresolved_not_counted_as_loss(self):
        rows=[{"status":"settled","fixture_id":"1","hit":True,"probability":.8},
              {"status":"unresolved","fixture_id":"2","hit":None,"probability":.9}]
        x=metrics(rows)
        self.assertEqual(x["settled"],1)
        self.assertEqual(x["unresolved"],1)
        self.assertEqual(x["hit_rate"],1.0)
        self.assertAlmostEqual(x["brier"],.04)
    def test_empty(self):
        self.assertIsNone(metrics([])["hit_rate"])
