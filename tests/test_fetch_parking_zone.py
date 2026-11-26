import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from fetch_parking_zone import parse_items  # noqa: E402

SAMPLE = """<response><header><resultCode>0000</resultCode></header><body><items>
<item><TITLE>20250824 입출차정보</TITLE><DESCRIPTION>입구:동2문입구#1, 입차시간:2025-08-24 13:48:38, 출구:동2문출구#1, 출차시간:2025-08-24 17:21:57</DESCRIPTION></item>
<item><TITLE>깨진 줄</TITLE><DESCRIPTION>알 수 없음</DESCRIPTION></item>
</items><numOfRows>10</numOfRows><pageNo>1</pageNo><totalCount>2411225</totalCount></body></response>"""


class ParseItems(unittest.TestCase):
    def test_문과_시각만_남긴다(self):
        total, rows = parse_items(SAMPLE)
        self.assertEqual(total, 2411225)
        self.assertEqual(rows, [{"in_gate": "동2문입구#1", "in_time": "2025-08-24 13:48:38",
                                 "out_gate": "동2문출구#1", "out_time": "2025-08-24 17:21:57"}])


if __name__ == "__main__":
    unittest.main()
