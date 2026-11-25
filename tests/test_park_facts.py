"""FAQ에서 주차 사실 뽑기 테스트 — 실행: python -m unittest tests/test_park_facts.py"""
import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from park_facts import extract  # noqa: E402

FAQ = pd.DataFrame([
    {"제목": "올림픽공원 내 주차시설은 어떻게 되나요", "내용": "올림픽공원은 2800여대의 차량이 주차할 수 있는 넓은 주차장을 보유하고 있으며 공원 내 주차매표소는 5개소로 북2문 동2문 남2문 남3문 남4문이 있습니다"},
    {"제목": "주차장 이용 및 요금은 어떻게 되나요", "내용": "일반승용차의 경우 10분당 600원씩 요금이 부과됩니다경차 장애인 국가유공자 저공해 다자녀(3자녀 이상) 차량은 이용요금이 50% 할인되며"},
    {"제목": "올림픽공원 이용시간이 어떻게 되나요", "내용": "차량을 이용하여출입하실 경우오전 6시~밤 10시까지 개방하고 있습니다(야간행사 개최시 제외)"},
    {"제목": "주차 예상 소요 시간은 어느 정도인가요", "내용": "공연시간 임박해서는 공원주변이 많이 혼잡하여 1시간가량 여유를 가지셔야 하며"},
    {"제목": "주차 후 공연장까지 오는 방법은 어떻게 되나요", "내용": "도보로 5분 정도 소요 됩니다"},
])


class ExtractTest(unittest.TestCase):
    def setUp(self):
        self.f = extract(FAQ)

    def test_capacity_and_booths(self):
        self.assertEqual(self.f["capacity"], 2800)
        self.assertEqual(self.f["booths"], ["북2문", "동2문", "남2문", "남3문", "남4문"])

    def test_fee(self):
        self.assertEqual((self.f["fee_per_10min"], self.f["discount_pct"]), (600, 50))

    def test_hours_and_tips(self):
        self.assertEqual((self.f["car_open"], self.f["car_close"]), (6, 22))
        self.assertEqual((self.f["spare_minutes"], self.f["walk_minutes"]), (60, 5))

    def test_every_fact_keeps_its_source_question(self):
        self.assertIn("주차장 이용 및 요금", self.f["sources"]["fee_per_10min"])


if __name__ == "__main__":
    unittest.main()
