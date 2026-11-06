import unittest
from github_models.abc_filter import evaluate

class FilterTests(unittest.TestCase):
    def test_abc_and_agreement(self):
        p={"predictions":[
            {"fixture_id":"a","model_id":"github-elo","p_home":.81,"p_draw":.10,"p_away":.09},
            {"fixture_id":"a","model_id":"callumfm-dixon-coles","p_home":.78,"p_draw":.12,"p_away":.10}]}
        result=evaluate(p,{"markets":[]})
        self.assertEqual(result["counts"],{"A":1,"B":1,"C":0})
    def test_invalid_probabilities_fail_closed(self):
        p={"predictions":[{"fixture_id":"a","model_id":"github-elo","p_home":.9,"p_draw":.9,"p_away":.9}]}
        with self.assertRaises(ValueError):
            evaluate(p,{"markets":[]})
    def test_binary_pair(self):
        p={"predictions":[]}
        events={"markets":[
            {"fixture_id":"a","model_id":"m","market":"goals","line":2.5,"selection":"over","probability":.82},
            {"fixture_id":"a","model_id":"m","market":"goals","line":2.5,"selection":"under","probability":.18}]}
        self.assertEqual(evaluate(p,events)["counts"],{"A":1,"B":1,"C":1})

if __name__=="__main__":
    unittest.main()
