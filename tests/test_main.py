import datetime as dt
import unittest

from flex2ics.__main__ import collect, month_chunks
from tests.helpers import day


class MonthChunksTest(unittest.TestCase):
    def test_range_is_split_on_month_boundaries(self):
        chunks = month_chunks(dt.date(2026, 9, 30), dt.date(2026, 11, 2))

        self.assertEqual(
            chunks,
            [
                (dt.date(2026, 9, 30), dt.date(2026, 9, 30)),
                (dt.date(2026, 10, 1), dt.date(2026, 10, 31)),
                (dt.date(2026, 11, 1), dt.date(2026, 11, 2)),
            ],
        )

    def test_single_day(self):
        self.assertEqual(month_chunks(dt.date(2026, 2, 28), dt.date(2026, 2, 28)), [(dt.date(2026, 2, 28),) * 2])


class FakeSession:
    def __init__(self, drop=None):
        self.drop = drop
        self.calls = []

    def work_schedules(self, start, end):
        self.calls.append((start, end))
        days = []
        current = start
        while current <= end:
            if current.isoformat() != self.drop:
                days.append(day(current.isoformat()))
            current += dt.timedelta(days=1)
        return days


class CollectTest(unittest.TestCase):
    def test_days_from_every_chunk_are_joined(self):
        session = FakeSession()

        days = collect(session, dt.date(2026, 9, 29), dt.date(2026, 10, 2), pause=0)

        self.assertEqual([d["date"] for d in days], ["2026-09-29", "2026-09-30", "2026-10-01", "2026-10-02"])
        self.assertEqual(len(session.calls), 2)

    def test_missing_day_stops_the_run(self):
        session = FakeSession(drop="2026-10-01")

        with self.assertRaises(RuntimeError):
            collect(session, dt.date(2026, 9, 29), dt.date(2026, 10, 2), pause=0)


if __name__ == "__main__":
    unittest.main()
