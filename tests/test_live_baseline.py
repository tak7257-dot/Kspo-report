"""실시간 비교 기준값 테스트 — 실행: python -m unittest tests/test_live_baseline.py"""
import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from live_baseline import build  # noqa: E402


def rows(dates, hour, values, month, kind="주말·휴일", show=True):
    return [{"날짜": d, "월": month, "요일유형": kind, "시": hour, "주차대수": v, "공연일": show, "이상일": False}
            for d, v in zip(dates, values)]


class BuildTest(unittest.TestCase):
    def setUp(self):
        r = rows(["2025-11-01", "2025-11-08", "2025-11-15"], 18, [4000, 4200, 4400], 11)
        r += rows(["2025-11-01", "2025-11-08"], 17, [3000, 3100], 11)              # 표본 2일 → null
        r += rows(["2025-11-22"], 18, [9999], 11, show=False)                       # 공연 없는 날은 빼기
        r += rows(["2025-08-02", "2025-08-09", "2025-08-16"], 18, [500, 500, 500], 8)  # 8월은 빼기
        self.out = build(pd.DataFrame(r))

    def test_median_of_show_days(self):
        self.assertEqual(self.out["show_day"]["11"]["weekend"][18], 4200)

    def test_few_samples_is_null(self):
        self.assertIsNone(self.out["show_day"]["11"]["weekend"][17])

    def test_all_months_pools_without_august(self):
        self.assertEqual(self.out["show_day"]["all"]["weekend"][18], 4200)

    def test_august_excluded(self):
        self.assertNotIn("8", self.out["show_day"])


if __name__ == "__main__":
    unittest.main()
