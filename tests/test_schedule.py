import datetime as dt
import unittest

from flex2ics.schedule import build_events
from tests.helpers import FORMS, TIME_OFF_NAMES, at, block, day, rest, time_off, work

D = "2026-10-19"


class BuildEventsTest(unittest.TestCase):
    def build(self, *days):
        events, skipped = build_events(list(days), FORMS, TIME_OFF_NAMES)
        return events, skipped

    def test_rest_goes_into_the_work_event_description(self):
        events, _ = self.build(day(D, work("1105", D, "10:00", "19:00"), rest(D, "12:00", "13:00")))

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].summary, "근무")
        self.assertEqual(events[0].start, at(D, "10:00"))
        self.assertEqual(events[0].end, at(D, "19:00"))
        self.assertEqual(events[0].description, "휴게 12:00-13:00")

    def test_remote_and_office_work_are_separate_events(self):
        events, _ = self.build(
            day(
                D,
                work("1107", D, "10:03", "13:00"),
                rest(D, "12:00", "13:00"),
                work("1105", D, "13:00", "18:34"),
            )
        )

        self.assertEqual([e.summary for e in events], ["재택근무", "근무"])
        self.assertEqual(events[0].description, "휴게 12:00-13:00")
        self.assertEqual(events[1].description, "")
        self.assertEqual(events[1].start, at(D, "13:00"))

    def test_several_rests_are_listed_in_time_order(self):
        events, _ = self.build(
            day(
                D,
                rest(D, "18:20", "19:20"),
                work("1105", D, "09:30", "22:10"),
                rest(D, "11:20", "12:20"),
            )
        )

        self.assertEqual(events[0].description, "휴게 11:20-12:20\n휴게 18:20-19:20")

    def test_touching_blocks_of_the_same_form_become_one_event(self):
        events, _ = self.build(day(D, work("1105", D, "12:00", "18:00"), work("1105", D, "09:00", "12:00")))

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].start, at(D, "09:00"))
        self.assertEqual(events[0].end, at(D, "18:00"))

    def test_same_form_split_by_another_form_keeps_unique_uids(self):
        events, _ = self.build(
            day(
                D,
                work("1105", D, "09:00", "11:00"),
                work("1106", D, "11:00", "14:00"),
                work("1105", D, "14:00", "18:00"),
            )
        )

        self.assertEqual([e.summary for e in events], ["근무", "외근", "근무"])
        self.assertEqual(
            [e.uid for e in events],
            [
                "2026-10-19-1105-0@flex2ics",
                "2026-10-19-1106-0@flex2ics",
                "2026-10-19-1105-1@flex2ics",
            ],
        )

    def test_rest_outside_every_work_block_goes_to_the_nearest_one(self):
        events, _ = self.build(
            day(
                D,
                work("1106", D, "09:00", "12:00"),
                rest(D, "12:00", "12:30"),
                work("1105", D, "13:00", "18:00"),
            )
        )

        self.assertEqual(events[0].description, "휴게 12:00-12:30")
        self.assertEqual(events[1].description, "")

    def test_memo_follows_the_rests(self):
        events, _ = self.build(
            day(D, work("1106", D, "10:00", "17:00", memo=" 고객사 미팅 "), rest(D, "12:00", "13:00"))
        )

        self.assertEqual(events[0].description, "휴게 12:00-13:00\n고객사 미팅")

    def test_day_off_without_blocks_has_no_event(self):
        events, skipped = self.build(day("2026-10-18", day_offs=("WEEKLY_HOLIDAY",)))

        self.assertEqual(events, [])
        self.assertEqual(skipped, {})

    def test_unknown_form_keeps_its_id_in_the_title(self):
        events, _ = self.build(day(D, work("9999", D, "10:00", "19:00")))

        self.assertEqual(events[0].summary, "근무 형태 9999")

    def test_unknown_block_type_is_counted_and_skipped(self):
        events, skipped = self.build(day(D, work("1105", D, "10:00", "19:00"), block("SOMETHING", "1", D, "10:00", "11:00")))

        self.assertEqual(len(events), 1)
        self.assertEqual(skipped, {"SOMETHING": 1})

    def test_all_day_block_becomes_an_all_day_event(self):
        events, _ = self.build(day(D, work("1104", D, "00:00", "00:00", all_day=True)))

        self.assertTrue(events[0].all_day)
        self.assertEqual(events[0].start, dt.date(2026, 10, 19))
        self.assertEqual(events[0].end, dt.date(2026, 10, 20))

    def test_timed_event_is_not_all_day(self):
        events, _ = self.build(day(D, work("1105", D, "10:00", "19:00")))

        self.assertFalse(events[0].all_day)


class TimeOffTest(unittest.TestCase):
    def build(self, *days):
        events, _ = build_events(list(days), FORMS, TIME_OFF_NAMES)
        return events

    def test_full_day_time_off_without_times_becomes_an_all_day_event(self):
        events = self.build(day("2026-03-10", time_off("ANNUAL_TIME_OFF", "199", "2026-03-10")))

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].summary, "연차")
        self.assertTrue(events[0].all_day)
        self.assertTrue(events[0].time_off)
        self.assertEqual(events[0].start, dt.date(2026, 3, 10))
        self.assertEqual(events[0].end, dt.date(2026, 3, 11))
        self.assertEqual(events[0].uid, "2026-03-10-timeoff-199-0@flex2ics")

    def test_half_day_time_off_sits_next_to_the_work_event(self):
        events = self.build(
            day(
                D,
                work("1105", D, "10:00", "15:00"),
                rest(D, "12:00", "13:00"),
                time_off("ANNUAL_TIME_OFF", "199", D, "15:00", "19:00"),
            )
        )

        self.assertEqual([(e.summary, e.time_off) for e in events], [("근무", False), ("연차", True)])
        self.assertEqual(events[0].description, "휴게 12:00-13:00")
        self.assertEqual(events[1].start, at(D, "15:00"))
        self.assertEqual(events[1].end, at(D, "19:00"))
        self.assertFalse(events[1].all_day)

    def test_morning_and_afternoon_halves_become_one_event(self):
        events = self.build(
            day(
                D,
                time_off("ANNUAL_TIME_OFF", "199", D, "15:00", "19:00"),
                time_off("ANNUAL_TIME_OFF", "199", D, "10:00", "15:00"),
            )
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].start, at(D, "10:00"))
        self.assertEqual(events[0].end, at(D, "19:00"))

    def test_each_day_of_a_long_time_off_is_its_own_event(self):
        events = self.build(
            day("2026-03-03", time_off("CUSTOM_TIME_OFF", "3188", "2026-03-03")),
            day("2026-03-04", time_off("CUSTOM_TIME_OFF", "3188", "2026-03-04")),
        )

        self.assertEqual([e.summary for e in events], ["리프레시", "리프레시"])
        self.assertEqual([e.start for e in events], [dt.date(2026, 3, 3), dt.date(2026, 3, 4)])

    def test_unknown_policy_falls_back_by_time_off_type(self):
        events = self.build(
            day("2026-03-03", time_off("ANNUAL_TIME_OFF", "999", "2026-03-03")),
            day("2026-03-04", time_off("CUSTOM_TIME_OFF", "998", "2026-03-04")),
        )

        self.assertEqual([e.summary for e in events], ["연차", "휴가"])

    def test_unconfirmed_time_off_keeps_its_status_in_the_description(self):
        events = self.build(
            day(D, time_off("ANNUAL_TIME_OFF", "199", D, "15:00", "19:00", status="IN_PROGRESS", memo=" 병원 "))
        )

        self.assertEqual(events[0].description, "flex 상태: IN_PROGRESS\n병원")

    def test_rest_on_a_day_without_work_is_dropped(self):
        events = self.build(day(D, time_off("ANNUAL_TIME_OFF", "199", D), rest(D, "12:00", "13:00")))

        self.assertEqual([e.summary for e in events], ["연차"])
        self.assertEqual(events[0].description, "")


if __name__ == "__main__":
    unittest.main()
