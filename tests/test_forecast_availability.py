import unittest

from scripts.afdj_core import forecast_availability


class ForecastAvailabilityTests(unittest.TestCase):
    def test_xml_and_html_equal(self):
        result = forecast_availability("0", "0", True)
        self.assertTrue(result["forecast_available"])
        self.assertTrue(result["xml_html_match"])
        self.assertEqual(result["quality_flag"], "valid")

    def test_xml_zero_html_blank(self):
        result = forecast_availability("0", "", True)
        self.assertFalse(result["forecast_available"])
        self.assertEqual(result["quality_flag"], "missing_forecast_encoded_as_zero")

    def test_xml_nonzero_html_blank(self):
        result = forecast_availability("12", "", True)
        self.assertFalse(result["forecast_available"])
        self.assertFalse(result["xml_html_match"])
        self.assertEqual(result["quality_flag"], "xml_html_availability_mismatch")

    def test_numeric_mismatch(self):
        result = forecast_availability("12", "13", True)
        self.assertTrue(result["forecast_available"])
        self.assertFalse(result["xml_html_match"])
        self.assertEqual(result["forecast_level_cm"], "12")

    def test_html_unavailable_nonzero_and_zero(self):
        nonzero = forecast_availability("12", None, False)
        zero = forecast_availability("0", None, False)
        self.assertTrue(nonzero["forecast_available"])
        self.assertEqual(nonzero["quality_flag"], "html_validation_unavailable")
        self.assertFalse(zero["forecast_available"])
        self.assertEqual(zero["quality_flag"], "ambiguous_xml_zero_html_unavailable")


if __name__ == "__main__": unittest.main()
