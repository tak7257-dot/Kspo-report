"""실시간 보정 되짚어 보기 테스트 — 실행: python -m unittest tests/test_nowcast_check.py"""
import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from nowcast_check import backtest  # noqa: E402


def day(date, scale):   # 평소 모양 × 그날 배율 (오후가 붐비면 저녁도 같은 비율로 붐비는 날들)
    return [{"날짜": date, "월": 10, "요일유형": "주말·휴일", "시": h, "주차대수": (1000 + 100 * h) * scale,
             "공연일": True, "이상일": False} for h in range(24)]


class BacktestTest(unittest.TestCase):
    def test_correction_beats_past_average_when_days_differ_by_scale(self):
        rows = []
        for i, sc in enumerate([0.8, 0.9, 1.0, 1.1, 1.2]):
            rows += day(f"2025-10-{i + 1:02d}", sc)
        r = backtest(pd.DataFrame(rows), pairs=[(15, 18)])
        one = r["weekend"][0]
        self.assertEqual((one["now"], one["target"], one["days"]), (15, 18, 5))
        self.assertLess(one["err_corrected"], one["err_past"])
        self.assertEqual(one["err_corrected"], 0.0)


if __name__ == "__main__":
    unittest.main()
