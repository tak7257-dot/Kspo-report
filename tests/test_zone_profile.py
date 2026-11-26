import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import zone_profile as zp  # noqa: E402


def car(in_gate, t_in, out_gate, t_out):
    return {"in_gate": in_gate, "in_time": t_in, "out_gate": out_gate, "out_time": t_out}


class ZoneProfile(unittest.TestCase):
    def test_문_이름에서_구역만(self):
        s = pd.Series(["동2문입구#1", "북2문CMB", "서1문출구#1"])
        self.assertEqual(zp.gate_zone(s).tolist(), ["동2", "북2", "서1"])

    def test_출차_몰림_비율(self):
        rows = []
        # 2025-05-03 공연 날: 21:30에 10대, 21:40에 5대, 21:50에 2대, 나머지 저녁 10분마다 0~1대
        for n, t in [(10, "21:30"), (5, "21:40"), (2, "21:50"), (1, "20:40")]:
            rows += [car("동2문입구#1", "2025-05-03 18:00:00", "동2문출구#1", f"2025-05-03 {t}:05")] * n
        d = zp.prepare(pd.DataFrame(rows))
        e = zp.exit_decay(d, {pd.Timestamp("2025-05-03")})
        self.assertEqual(e["저녁수"], 1)
        self.assertEqual(e["최대출차_10분_중앙값"], 10)
        self.assertEqual(e["ratio"][:3], [1.0, 0.5, 0.2])

    def test_문별_비중과_머문_시간(self):
        rows = [car("북2문입구#1", "2025-05-03 18:10:00", "북2문출구#1", "2025-05-03 21:40:00")] * 3 + \
               [car("동2문입구#2", "2025-05-03 18:20:00", "남2문출구#1", "2025-05-03 22:20:00")]
        d = zp.prepare(pd.DataFrame(rows))
        days = pd.DataFrame({"날짜": [pd.Timestamp("2025-05-03")], "요일유형": ["주말·휴일"], "공연일": [True], "이상일": [False]})
        g = zp.gates(d, days)["weekend"]
        self.assertEqual(g["arrive"]["show"]["zones"][0], {"zone": "북2", "share": 0.75, "per_day": 3.0})
        self.assertEqual({z["zone"] for z in g["leave"]["show"]["zones"]}, {"북2", "남2"})
        s = zp.stay(d, {pd.Timestamp("2025-05-03")})
        self.assertEqual((s["대수"], s["median"]), (4, 210))


if __name__ == "__main__":
    unittest.main()
