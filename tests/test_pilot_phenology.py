from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "01_script" / "06_pilot_phenology.py"
SPEC = importlib.util.spec_from_file_location("pilot_phenology", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class PilotPhenologyTests(unittest.TestCase):
    def test_parse_dates_uses_true_elapsed_days_across_leap_year(self) -> None:
        values = MODULE.parse_dates(
            (
                "EVI_2003_12_19",
                "EVI_2004_01_01",
                "EVI_2004_12_18",
                "EVI_2005_01_01",
            ),
            2001,
        )
        self.assertEqual(values[1] - values[0], 13)
        self.assertEqual(values[3] - values[2], 14)
        self.assertEqual(values[3] - values[1], 366)

    def test_parse_dates_rejects_missing_description(self) -> None:
        with self.assertRaises(ValueError):
            MODULE.parse_dates((None,), 2001)


if __name__ == "__main__":
    unittest.main()
