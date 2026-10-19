"""캘린더 일정을 iCalendar(RFC 5545) 텍스트로 쓴다.

구글 캘린더 구독이 읽으면 되므로 필요한 속성만 쓴다. 시각은 전부 UTC(Z)로 적어
VTIMEZONE 을 넣지 않는다. 보여 줄 때는 구독하는 쪽이 자기 시간대로 바꾼다.
"""

import datetime as dt

from .schedule import KST


def escape(text):
    """TEXT 값에서 의미가 있는 문자를 이스케이프한다. 백슬래시를 가장 먼저 바꿔야 한다."""
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def fold(line):
    """한 줄을 75 옥텟 이하로 접는다.

    한국어는 글자 하나가 3 옥텟이라 글자 수가 아니라 UTF-8 길이로 잘라야 하고,
    글자 중간에서 자르면 안 된다. 이어지는 줄은 맨 앞 공백 한 칸까지 75 옥텟이다.
    """
    if len(line.encode("utf-8")) <= 75:
        return line
    parts = []
    current = ""
    size = 0
    limit = 75
    for char in line:
        width = len(char.encode("utf-8"))
        if size + width > limit:
            parts.append(current)
            current = ""
            size = 0
            limit = 74
        current += char
        size += width
    parts.append(current)
    return "\r\n ".join(parts)


def _utc(moment):
    return moment.astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _sort_key(event):
    if event.all_day:
        return dt.datetime.combine(event.start, dt.time(0), KST), event.uid
    return event.start, event.uid


def render(events, name, now):
    """일정 목록을 ICS 텍스트로 만든다. now 는 DTSTAMP 에 쓸 생성 시각이다."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//KENNYSOFT//flex2ics//KO",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:" + escape(name),
        "X-WR-TIMEZONE:Asia/Seoul",
        "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
        "X-PUBLISHED-TTL:PT12H",
    ]
    stamp = _utc(now)
    for event in sorted(events, key=_sort_key):
        lines.append("BEGIN:VEVENT")
        lines.append("UID:" + event.uid)
        lines.append("DTSTAMP:" + stamp)
        if event.all_day:
            lines.append("DTSTART;VALUE=DATE:" + event.start.strftime("%Y%m%d"))
            lines.append("DTEND;VALUE=DATE:" + event.end.strftime("%Y%m%d"))
        else:
            lines.append("DTSTART:" + _utc(event.start))
            lines.append("DTEND:" + _utc(event.end))
        lines.append("SUMMARY:" + escape(event.summary))
        if event.description:
            lines.append("DESCRIPTION:" + escape(event.description))
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "".join(fold(line) + "\r\n" for line in lines)
