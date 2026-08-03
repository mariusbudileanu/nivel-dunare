import unittest
from pathlib import Path

from scripts.afdj_core import CRITICAL_PATHS, flatten_xml, parse_xml, xml_schema


ROOT = Path(__file__).resolve().parents[1]
XML = (ROOT / "_audit_source/raw/afdj_latest_raw.xml").read_bytes()


class XmlParserTests(unittest.TestCase):
    def test_real_root_items_and_identifiers(self):
        root, items = parse_xml(XML)
        self.assertEqual(root.tag, "response")
        self.assertEqual(len(items), 23)
        self.assertEqual(len({item.findtext("uuid/value") for item in items}), 23)
        self.assertTrue(all(item.findtext("nid/value") for item in items))

    def test_flattening_preserves_full_paths_and_attribute(self):
        rows, columns = flatten_xml(XML)
        self.assertEqual(len(rows), 23)
        self.assertIn("item@key", columns)
        self.assertIn("item/type/target_uuid", columns)
        self.assertIn("item/feeds_item/hash", columns)
        self.assertIn("item/path/alias", columns)
        self.assertIn("item/field_geolocation_demo_single/lat", columns)
        self.assertGreaterEqual(len(columns), 55)

    def test_all_critical_paths_present(self):
        rows, columns = flatten_xml(XML)
        schema = xml_schema(XML, rows, columns)
        self.assertEqual(set(schema["critical_paths_present"]), set(CRITICAL_PATHS))
        self.assertTrue(all(schema["critical_paths_present"].values()))
        self.assertEqual(schema["tag_counts"]["item"], 23)


if __name__ == "__main__":
    unittest.main()
