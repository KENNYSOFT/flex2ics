import datetime as dt
import unittest

from flex2ics.ics import escape, fold, render
from flex2ics.schedule import Event
from tests.helpers import at

NOW = dt.datetime(2026, 10, 19, 6, 0, tzinfo=dt.timezone.utc)


class EscapeTest(unittest.TestCase):
    def test_special_characters_are_escaped(self):
        self.assertEqual(escape("a,b;c\\d\ne"), "a\\,b\\;c\\\\d\\ne")


class FoldTest(unittest.TestCase):
    def test_short_line_is_untouched(self):
        self.assertEqual(fold("SUMMARY:근무"), "SUMMARY:근무")

    def test_continuation_lines_count_the_leading_space(self):
        line = "DESCRIPTION:" + "a" * 200

        physical = fold(line).split("\r\n")

        self.assertEqual([len(part) for part in physical], [75, 75, 64])

    def test_long_korean_line_is_folded_on_character_boundaries(self):
        line = "DESCRIPTION:" + "휴게 시간과 메모가 길게 이어지는 설명" * 6

        folded = fold(line)

        physical = folded.split("\r\n")
        self.assertGreater(len(physical), 1)
        for index, part in enumerate(physical):
            self.assertLessEqual(len(part.encode("utf-8")), 75)
            if index:
                self.assertTrue(part.startswith(" "))
        self.assertEqual(folded.replace("\r\n ", ""), line)


class RenderTest(unittest.TestCase):
    def render(self, *events):
        return render(list(events), "flex 근무", NOW)

    def test_timed_event_is_written_in_utc(self):
        text = self.render(
            Event(
                uid="2026-10-19-1105-0@flex2ics",
                summary="근무",
                start=at("2026-10-19", "10:00"),
                end=at("2026-10-19", "19:00"),
                description="휴게 12:00-13:00",
            )
        )

        self.assertIn("DTSTART:20261019T010000Z\r\n", text)
        self.assertIn("DTEND:20261019T100000Z\r\n", text)
        self.assertIn("SUMMARY:근무\r\n", text)
        self.assertIn("DESCRIPTION:휴게 12:00-13:00\r\n", text)
        self.assertIn("DTSTAMP:20261019T060000Z\r\n", text)
        self.assertIn("X-WR-CALNAME:flex 근무\r\n", text)

    def test_all_day_event_uses_dates(self):
        text = self.render(
            Event(
                uid="2026-10-19-1104-0@flex2ics",
                summary="출장",
                start=dt.date(2026, 10, 19),
                end=dt.date(2026, 10, 20),
            )
        )

        self.assertIn("DTSTART;VALUE=DATE:20261019\r\n", text)
        self.assertIn("DTEND;VALUE=DATE:20261020\r\n", text)
        self.assertNotIn("DESCRIPTION", text)

    def test_every_line_ends_with_crlf(self):
        text = self.render(
            Event(
                uid="a@flex2ics",
                summary="근무",
                start=at("2026-10-19", "10:00"),
                end=at("2026-10-19", "19:00"),
                description="휴게 12:00-13:00\n" + "긴 메모" * 30,
            )
        )

        self.assertTrue(text.startswith("BEGIN:VCALENDAR\r\n"))
        self.assertTrue(text.endswith("END:VCALENDAR\r\n"))
        self.assertNotIn("\n", text.replace("\r\n", ""))

    def test_events_are_sorted_by_start_across_all_day_and_timed(self):
        text = self.render(
            Event(uid="b@flex2ics", summary="근무", start=at("2026-10-20", "10:00"), end=at("2026-10-20", "19:00")),
            Event(uid="a@flex2ics", summary="출장", start=dt.date(2026, 10, 19), end=dt.date(2026, 10, 20)),
        )

        self.assertLess(text.index("UID:a@flex2ics"), text.index("UID:b@flex2ics"))


if __name__ == "__main__":
    unittest.main()
