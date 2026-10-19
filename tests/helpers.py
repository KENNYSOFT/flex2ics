"""flex 응답과 같은 모양의 테스트 데이터를 만든다. 값은 전부 지어낸 것이다."""

import datetime as dt

KST = dt.timezone(dt.timedelta(hours=9))

FORMS = {"1104": "출장", "1105": "근무", "1106": "외근", "1107": "재택근무", "1108": "휴게"}

TIME_OFF_NAMES = {"199": "연차", "3176": "공가", "3188": "리프레시"}


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


def time_off(kind, policy, date, start=None, end=None, status="APPROVAL_COMPLETED", memo=None):
    """휴가 블록. start 가 없으면 종일 휴가이고, flex 처럼 시각 필드를 아예 넣지 않는다."""
    value = {
        "allDay": start is None,
        "status": status,
        "timeOffEventId": "1",
        "timeOffPolicyId": policy,
        "timeOffRegisterUnit": "DAY" if start is None else "HALF_DAY_PM",
        "timezoneAtRegistration": "Asia/Seoul",
        "usedMinutes": 480 if start is None else 240,
        "usedPaidMinutes": 480 if start is None else 240,
        "restMinutes": 0,
        "metadata": {},
        "approval": {"status": "APPROVED"},
        "cancelApprovals": [],
    }
    if start is not None:
        value["startTimestamp"] = {"zoneId": "Asia/Seoul", "timestamp": ms(date, start)}
        value["endTimestampExclusive"] = {"zoneId": "Asia/Seoul", "timestamp": ms(date, end)}
    if memo is not None:
        value["memo"] = memo
    return {"type": kind, "value": value}


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
