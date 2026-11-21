import unittest
from github_models.bookings_settlement_pilot_20261121 import stop_after_api_error

class TestPilotFailClosed(unittest.TestCase):
    def test_stop_on_http_500_and_503(self):
        for status in ("http_500","http_503","http_502","http_401","http_403","http_429"):
            self.assertTrue(stop_after_api_error(status))
    def test_continue_only_on_non_terminal(self):
        for status in (None,"http_400","invalid_response"):
            self.assertFalse(stop_after_api_error(status))

if __name__=="__main__":
    unittest.main()
