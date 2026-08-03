import json
import unittest

from scripts.afdj_core import compare_schemas


class SchemaChangeTests(unittest.TestCase):
    def test_new_noncritical_path_is_reported_not_critical(self):
        old = {"leaf_paths": ["item/uuid/value"], "tag_counts": {"uuid": 1}}
        new = {"leaf_paths": ["item/uuid/value", "item/new/value"], "tag_counts": {"uuid": 1, "new": 1}, "xml_sha256": "x"}
        change = compare_schemas(old, new, "now")
        self.assertEqual(change["severity"], "info")
        self.assertIn("item/new/value", json.loads(change["added_leaf_paths"]))

    def test_removed_critical_path_is_critical(self):
        old = {"leaf_paths": ["item/uuid/value"], "tag_counts": {"uuid": 1}}
        new = {"leaf_paths": [], "tag_counts": {}, "xml_sha256": "x"}
        change = compare_schemas(old, new, "now")
        self.assertEqual(change["severity"], "critical")
        self.assertIn("uuid/value", json.loads(change["critical_removed"]))


if __name__ == "__main__": unittest.main()
