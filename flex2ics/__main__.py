"""flex 의 내 근무를 받아 ICS 파일 하나로 쓴다.

    python -m flex2ics --out site/work.ics

로그인 정보는 환경 변수 FLEX_EMAIL, FLEX_PASSWORD 로 받는다. 터미널에서 직접
돌릴 때 둘 중 없는 것은 입력받고, 비밀번호는 화면에 보이지 않게 받는다.

받는 범위는 한국 날짜로 오늘을 기준으로 앞뒤 며칠이다. 구독하는 캘린더는 파일에
없는 일정을 지우므로 이 범위를 지난 기록은 캘린더에서도 사라진다.

어디서 실패하든 파일을 쓰지 않고 0 이 아닌 코드로 끝난다. 워크플로는 그 단계에서
멈추므로 이미 게시된 파일은 빈 캘린더로 덮이지 않고 그대로 남는다.
"""

import argparse
import datetime as dt
import getpass
import os
import sys
import time
import uuid

from . import client, ics, schedule

# Windows 콘솔 기본 코드페이지(cp949)로는 한국어 출력이 깨진다.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

CALENDAR_NAME = "flex 근무"


def month_chunks(start, end):
    """start 부터 end 까지를 달력의 달 단위로 나눈다. 웹 앱도 한 번에 한 달 남짓만 부른다."""
    chunks = []
    cursor = start
    while cursor <= end:
        next_month = (cursor.replace(day=1) + dt.timedelta(days=32)).replace(day=1)
        last = min(end, next_month - dt.timedelta(days=1))
        chunks.append((cursor, last))
        cursor = last + dt.timedelta(days=1)
    return chunks


def collect(session, start, end, pause=0.5):
    """기간 전체의 날짜별 일정을 모은다. 요청한 날짜가 하나라도 빠지면 멈춘다.

    날짜가 빠진 응답으로 파일을 쓰면 그날의 일정이 캘린더에서 조용히 지워진다.
    """
    days = []
    for index, (first, last) in enumerate(month_chunks(start, end)):
        if index and pause:
            time.sleep(pause)
        chunk = session.work_schedules(first, last)
        expected = {(first + dt.timedelta(days=n)).isoformat() for n in range((last - first).days + 1)}
        received = {day["date"] for day in chunk}
        if received != expected:
            raise RuntimeError(
                "%s..%s 응답의 날짜가 요청과 다르다 (요청 %d일, 응답 %d일)"
                % (first, last, len(expected), len(received))
            )
        days.extend(chunk)
    return days


def credentials():
    """로그인 정보를 환경 변수에서 읽고, 없으면 터미널에서 입력받는다."""
    email = os.environ.get("FLEX_EMAIL", "").strip()
    password = os.environ.get("FLEX_PASSWORD", "")
    if (not email or not password) and not sys.stdin.isatty():
        raise SystemExit("FLEX_EMAIL 과 FLEX_PASSWORD 를 환경 변수로 넣어야 한다.")
    if not email:
        email = input("flex 이메일: ").strip()
    if not password:
        password = getpass.getpass("flex 비밀번호: ")
    return email, password


def device_id(email):
    """로그인할 때 보낼 기기 id 를 준다.

    실행마다 같은 값이어야 flex 쪽에서 매번 새 기기로 보이지 않는다. 그래서 무작위로
    만들지 않고 이메일에서 정해지는 값을 쓴다. FLEX_DEVICE_ID 를 주면 그것을 쓴다.
    """
    configured = os.environ.get("FLEX_DEVICE_ID", "").strip()
    if configured:
        return configured
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "https://github.com/KENNYSOFT/flex2ics#" + email))


def write(path, text):
    """파일을 원자적으로 쓴다. 줄바꿈은 ICS 규격대로 이미 CRLF 이므로 바꾸지 않는다."""
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    temp = path + ".tmp"
    with open(temp, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    os.replace(temp, path)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="flex2ics", description="flex 의 내 근무를 ICS 파일로 쓴다.")
    parser.add_argument("--out", required=True, help="쓸 ICS 파일 경로")
    parser.add_argument("--past-days", type=int, default=365, help="오늘 전으로 받을 날 수 (기본 365)")
    parser.add_argument("--future-days", type=int, default=90, help="오늘 뒤로 받을 날 수 (기본 90)")
    args = parser.parse_args(argv)

    now = dt.datetime.now(dt.timezone.utc)
    today = now.astimezone(schedule.KST).date()
    start = today - dt.timedelta(days=args.past_days)
    end = today + dt.timedelta(days=args.future_days)

    email, password = credentials()
    session = client.login(email, password, device_id(email))
    work_names = session.work_forms()
    time_off_names = session.time_off_names()
    days = collect(session, start, end)
    events, skipped = schedule.build_events(days, work_names, time_off_names)
    if not events:
        raise SystemExit("%s..%s 에 일정이 하나도 없다. 빈 캘린더를 게시하지 않고 멈춘다." % (start, end))

    write(args.out, ics.render(events, CALENDAR_NAME, now))
    time_off = sum(1 for event in events if event.time_off)
    print("%s..%s 일정 %d건(근무 %d건, 휴가 %d건)을 썼다." % (start, end, len(events), len(events) - time_off, time_off))
    if skipped:
        counts = ", ".join("%s %d건" % (kind, n) for kind, n in sorted(skipped.items(), key=lambda item: str(item[0])))
        print("모르는 종류의 블록을 건너뛰었다: %s" % counts)


if __name__ == "__main__":
    main()
