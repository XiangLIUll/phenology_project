from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

import numpy as np


SCRIPT = Path(__file__).resolve().parents[1] / "01_script" / "06_pilot_phenology.py"
SPEC = importlib.util.spec_from_file_location("pilot_phenology", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class PilotPhenologyTests(unittest.TestCase):
    def test_cdts_08_metric_contract(self) -> None:
        self.assertEqual(len(MODULE.METRICS), 21)
        self.assertEqual(MODULE.METRICS[-2:], ("R2", "RMSE"))

    def test_45_day_filter_retains_annual_synthetic_seasons(self) -> None:
        dates = 1.0 + 16.0 * np.arange(575)
        values = (
            0.2
            + 0.3
            * np.maximum(0.0, np.sin(2 * np.pi * (dates - 80.0) / 365.0))
        )[None, :]
        output = MODULE.fit_phenology_batch(
            values_array=values,
            dates_array=dates,
            curve_type=int(MODULE.CurveType.BECK),
            max_seasons=25,
            whittaker_lambda=5.0,
            apply_whittaker=True,
            min_season_length=45,
            min_amplitude=0.1,
            min_pixel_amplitude=0.1,
            n_jobs=1,
        )
        self.assertEqual(output.shape, (21, 1, 25))
        self.assertTrue(np.isfinite(output).all())

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
