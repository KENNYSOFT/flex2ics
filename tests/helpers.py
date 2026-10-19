"""flex 응답과 같은 모양의 테스트 데이터를 만든다. 값은 전부 지어낸 것이다."""

import datetime as dt

KST = dt.timezone(dt.timedelta(hours=9))

FORMS = {"1104": "출장", "1105": "근무", "1106": "외근", "1107": "재택근무", "1108": "휴게"}


def ms(date, hhmm):
    hour, minute = (int(part) for part in hhmm.split(":"))
    moment = dt.datetime.fromisoformat(date).replace(hour=hour, minute=minute, tzinfo=KST)
    return int(moment.timestamp() * 1000)


def block(kind, form, date, start, end, memo="", all_day=False):
    return {
        "type": kind,
        "value": {
            "startTimestamp": {"zoneId": "Asia/Seoul", "timestamp": ms(date, start)},
            "endTimestampExclusive": {"zoneId": "Asia/Seoul", "timestamp": ms(date, end)},
            "workFormId": form,
            "workRecordEventId": "-1",
            "eventStatus": "PLAN",
            "eventSource": "AUTO_PLAN",
            "memo": memo,
            "metadata": {"referenceId": "-1"},
            "allDay": all_day,
        },
    }


def work(form, date, start, end, **kwargs):
    return block("WORK", form, date, start, end, **kwargs)


def rest(date, start, end):
    return block("REST", "1108", date, start, end)


def day(date, *blocks, day_offs=()):
    return {
        "date": date,
        "timezone": "Asia/Seoul",
        "dayOffs": [{"type": kind} for kind in day_offs],
        "timeBlocks": list(blocks),
        "legalTimeBlocks": [],
        "approvals": [],
    }


def at(date, hhmm):
    return dt.datetime.fromtimestamp(ms(date, hhmm) / 1000, KST)
