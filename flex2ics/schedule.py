"""flex 의 하루 근무 블록을 캘린더 일정으로 바꾼다.

flex 는 날짜마다 timeBlocks 를 준다. 근무 블록(type WORK)은 근무 형태(workFormId)
마다 따로 오고, 휴게 블록(type REST)은 자기를 품은 근무 블록과 시간이 겹친 채로
따로 온다. 예를 들어 10:00-19:00 근무 블록이 있고 12:00-13:00 휴게 블록이 그 안에
또 있다. 오전 재택근무, 오후 근무처럼 형태가 바뀌는 날은 근무 블록이 둘이다.

그래서 근무 블록 하나를 일정 하나로 만든다. 휴게는 일정으로 만들지 않고, 자기와
가장 많이 겹치는 근무 일정의 설명에 시각만 적는다. 형태가 같은 근무 블록이
맞닿아 있으면 한 일정으로 합친다.

휴가는 type 이 ANNUAL_TIME_OFF(연차)나 CUSTOM_TIME_OFF(그 밖의 휴가)인 블록으로
온다. 반차는 시각이 있고, 종일 휴가는 시각 없이 allDay 만 있다. 여러 날 휴가는
날짜마다 블록이 따로 오므로 날짜마다 종일 일정을 하나씩 만든다. 같은 휴가가
맞닿아 있으면(오전 반차와 오후 반차) 근무처럼 한 일정으로 합친다.

아직 지나지 않은 날에는 flex 가 근무 규칙대로 넣어 둔 계획(eventStatus PLAN)이
오고, 지난 날짜에는 실제 기록(RECORD)이 온다. 내 근무 화면이 둘 다 보여 주므로
둘 다 일정으로 만든다. UID 를 날짜와 근무 형태로 만들어서, 오늘의 계획이 기록으로
바뀌어도 캘린더에서는 같은 일정이 고쳐진다.
"""

import collections
import dataclasses
import datetime as dt

# flex 는 시각마다 zoneId 를 주지만 이 저장소가 다루는 것은 한국 근무뿐이다.
# 한국은 일광 절약 시간이 없어 고정 오프셋으로 충분하고, Windows 에서 tzdata
# 패키지 없이도 돈다.
KST = dt.timezone(dt.timedelta(hours=9))

# 휴가 블록의 status 중 이것만 확인했다. 다른 값이면 확정되지 않은 휴가일 수
# 있어 그 값을 설명에 그대로 적는다.
TIME_OFF_CONFIRMED = "APPROVAL_COMPLETED"


@dataclasses.dataclass(frozen=True)
class Event:
    """캘린더 일정 하나. 종일 일정이면 start 와 end 가 date 이고 end 는 다음 날이다."""

    uid: str
    summary: str
    start: dt.date
    end: dt.date
    description: str = ""
    time_off: bool = False

    @property
    def all_day(self):
        return not isinstance(self.start, dt.datetime)


@dataclasses.dataclass(frozen=True)
class _Block:
    kind: str
    form_id: str
    start: dt.datetime
    end: dt.datetime
    all_day: bool
    memos: tuple
    fallback: str


def _moment(value):
    return dt.datetime.fromtimestamp(value["timestamp"] / 1000, KST)


def _time_off(date, kind, value):
    """휴가 블록을 읽는다. 종일 휴가는 시각이 없어 그날 0시부터 다음 날 0시로 둔다."""
    if value.get("allDay") or "startTimestamp" not in value:
        start = dt.datetime.combine(dt.date.fromisoformat(date), dt.time(0), KST)
        end = start + dt.timedelta(days=1)
        all_day = True
    else:
        start = _moment(value["startTimestamp"])
        end = _moment(value["endTimestampExclusive"])
        all_day = False
    memos = []
    status = value.get("status")
    if status and status != TIME_OFF_CONFIRMED:
        memos.append("flex 상태: %s" % status)
    memo = (value.get("memo") or "").strip()
    if memo:
        memos.append(memo)
    return _Block(
        kind="TIME_OFF",
        form_id=str(value.get("timeOffPolicyId")),
        start=start,
        end=end,
        all_day=all_day,
        memos=tuple(memos),
        fallback="연차" if kind == "ANNUAL_TIME_OFF" else "휴가",
    )


def _blocks(day):
    """하루의 근무, 휴게, 휴가 블록을 읽는다. 그 밖의 종류는 종류별로 세고 건너뛴다."""
    blocks = []
    skipped = collections.Counter()
    for item in day.get("timeBlocks") or []:
        kind = item.get("type")
        value = item.get("value") or {}
        if kind in ("WORK", "REST"):
            memo = (value.get("memo") or "").strip()
            form_id = str(value.get("workFormId"))
            blocks.append(
                _Block(
                    kind=kind,
                    form_id=form_id,
                    start=_moment(value["startTimestamp"]),
                    end=_moment(value["endTimestampExclusive"]),
                    all_day=bool(value.get("allDay")),
                    memos=(memo,) if memo else (),
                    fallback="근무 형태 %s" % form_id,
                )
            )
        elif kind and kind.endswith("_TIME_OFF"):
            blocks.append(_time_off(day["date"], kind, value))
        else:
            skipped[kind] += 1
    return blocks, skipped


def _merge(blocks):
    """형태가 같고 맞닿거나 겹치는 블록을 하나로 합친다."""
    merged = []
    for block in sorted(blocks, key=lambda b: (b.start, b.end)):
        last = merged[-1] if merged else None
        if (
            last is not None
            and last.form_id == block.form_id
            and last.all_day == block.all_day
            and block.start <= last.end
        ):
            memos = last.memos + tuple(m for m in block.memos if m not in last.memos)
            merged[-1] = dataclasses.replace(last, end=max(last.end, block.end), memos=memos)
        else:
            merged.append(block)
    return merged


def _owner(rest, works):
    """휴게 블록을 붙일 근무 블록의 순번을 고른다.

    가장 많이 겹치는 근무 블록에 붙인다. 겹치는 것이 없으면 시간상 가장 가까운
    근무 블록에 붙인다. 같으면 먼저 시작한 쪽이다.
    """

    def overlap(index):
        work = works[index]
        return min(rest.end, work.end) - max(rest.start, work.start)

    def gap(index):
        work = works[index]
        return max(work.start - rest.end, rest.start - work.end)

    best = max(range(len(works)), key=overlap)
    if overlap(best) > dt.timedelta(0):
        return best
    return min(range(len(works)), key=gap)


def _all_day_range(block):
    start = block.start.date()
    end = block.end.date()
    if block.end.time() != dt.time(0):
        end += dt.timedelta(days=1)
    if end <= start:
        end = start + dt.timedelta(days=1)
    return start, end


def _events(date, prefix, blocks, rests, names):
    """합친 블록을 일정으로 만든다. 같은 날 같은 형태가 또 나오면 UID 끝 번호를 올린다."""
    events = []
    seen = {}
    for block, own_rests in zip(blocks, rests):
        lines = ["휴게 %s-%s" % (r.start.strftime("%H:%M"), r.end.strftime("%H:%M")) for r in own_rests]
        lines.extend(block.memos)
        nth = seen.get(block.form_id, 0)
        seen[block.form_id] = nth + 1
        if block.all_day:
            start, end = _all_day_range(block)
        else:
            start, end = block.start, block.end
        events.append(
            Event(
                uid="%s-%s%s-%d@flex2ics" % (date, prefix, block.form_id, nth),
                summary=names.get(block.form_id) or block.fallback,
                start=start,
                end=end,
                description="\n".join(lines),
                time_off=block.kind == "TIME_OFF",
            )
        )
    return events


def _day_events(day, work_names, time_off_names):
    blocks, skipped = _blocks(day)

    works = _merge([b for b in blocks if b.kind == "WORK"])
    rests = [[] for _ in works]
    if works:
        for rest in sorted((b for b in blocks if b.kind == "REST"), key=lambda b: b.start):
            rests[_owner(rest, works)].append(rest)

    time_offs = _merge([b for b in blocks if b.kind == "TIME_OFF"])

    events = _events(day["date"], "", works, rests, work_names)
    events.extend(_events(day["date"], "timeoff-", time_offs, [[] for _ in time_offs], time_off_names))
    return events, skipped


def build_events(days, work_names, time_off_names):
    """날짜별 일정 목록을 캘린더 일정으로 바꾼다.

    (일정 목록, 건너뛴 블록 수를 종류별로 센 Counter) 를 준다.
    """
    events = []
    skipped = collections.Counter()
    for day in days:
        day_events, day_skipped = _day_events(day, work_names, time_off_names)
        events.extend(day_events)
        skipped.update(day_skipped)
    return events, skipped
