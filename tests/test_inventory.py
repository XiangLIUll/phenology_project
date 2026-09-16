from __future__ import annotations

import importlib.util
import re
import sys
import unittest
from datetime import date
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "01_script" / "01_inventory_evi.py"
SPEC = importlib.util.spec_from_file_location("inventory_evi", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class InventoryTests(unittest.TestCase):
    def test_time_index_preserves_leap_days(self) -> None:
        rows = MODULE.build_time_rows((date(2004, 2, 18), date(2004, 3, 5)))
        self.assertEqual(rows[0]["DOY"], 49)
        self.assertEqual(rows[1]["DOY"], 65)
        self.assertEqual(
            rows[1]["days_since_base_plus_one"]
            - rows[0]["days_since_base_plus_one"],
            16,
        )

    def test_parse_band_dates(self) -> None:
        pattern = re.compile(
            r"^EVI_(?P<year>\d{4})_(?P<month>\d{2})_(?P<day>\d{2})$"
        )
        dates, anomalies = MODULE.parse_band_dates(
            [{"band": 1, "description": "EVI_2001_01_01"}], pattern
        )
        self.assertEqual(dates, (date(2001, 1, 1),))
        self.assertFalse(anomalies)


if __name__ == "__main__":
    unittest.main()
