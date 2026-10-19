# flex2ics

flex 의 "내 근무" 를 ICS 파일 하나로 만들어 GitHub Pages 에 올린다. 구글 캘린더에서 그 주소를 구독하면 근무, 재택근무, 외근이 일정으로 보인다.

## 자동 수집과 flex 약관

flex 서비스 이용약관(2026-09-21 시행)은 플렉스의 동의 없이 자동화 수단으로 flex 에 접근해 정보를 수집하는 것을 금지하고, 이 의무는 구성원에게도 적용된다. 이 저장소는 웹 앱이 쓰는 API 를 부르므로 매일 도는 예약 실행을 기본으로 꺼 두었다. 플렉스의 동의를 받은 뒤에 켠다.

## 캘린더에 들어가는 것

- 근무 블록 하나가 일정 하나다. 일정 이름은 근무 형태 이름(근무, 재택근무, 외근, 출장)이다.
- 형태가 같은 블록이 맞닿아 있으면 한 일정으로 합치고, 오전 재택근무 오후 근무처럼 형태가 바뀌면 따로 둔다.
- 휴게는 일정으로 만들지 않는다. 그 휴게를 품은 근무 일정의 메모에 `휴게 12:00-13:00` 처럼 적고, flex 에 적은 메모가 있으면 그 아래에 적는다.
- 지난 날짜는 실제 기록이, 앞으로의 날짜는 flex 가 근무 규칙대로 넣어 둔 계획이 들어간다. 계획이 기록으로 바뀌면 같은 일정이 고쳐진다.
- 한국 날짜로 오늘 기준 지난 365일부터 앞으로 90일까지 담는다. 그보다 오래된 기록은 캘린더에서도 사라진다.
- 휴일과 휴가는 넣지 않는다.

## 설정

1. Settings > Secrets and variables > Actions 의 Secrets 에 세 값을 넣는다.
   - `FLEX_EMAIL`, `FLEX_PASSWORD`: flex 로그인 정보. 실행할 때마다 새로 로그인하므로 세션이나 쿠키를 넣어 둘 필요가 없다.
   - `FLEX_ICS_NAME`: 게시할 파일 이름(확장자 제외). 구독 주소가 이 이름으로 정해지므로 남이 짐작할 수 없는 값으로 둔다.
2. Settings > Pages 에서 Source 를 GitHub Actions 로 두고, Custom domain 에 `flex.kennysoft.kr` 를 넣는다. DNS 에는 `flex` 의 CNAME 을 `kennysoft.github.io` 로 둔다.
3. Actions 의 "근무 캘린더 게시" 를 수동으로 실행해 게시되는지 확인한다.
4. 구글 캘린더의 다른 캘린더 > URL로 추가 에 `https://flex.kennysoft.kr/<FLEX_ICS_NAME>.ics` 를 넣는다. 구독 캘린더를 다시 읽는 주기는 구글이 정하므로 반영이 하루 가까이 늦을 수 있다.
5. 플렉스의 동의를 받으면 Settings > Secrets and variables > Actions 의 Variables 에 `SCHEDULE_ENABLED` 를 `true` 로 둔다. 그때부터 매일 KST 06:00 에 돈다.

`FLEX_ICS_NAME` 은 이렇게 만들 수 있다.

```bash
python -c "import secrets; print(secrets.token_urlsafe(24))"
```

## 공개 저장소에서 보이는 것

Actions 로그에는 날짜 범위와 일정 건수만 찍힌다. 토큰, 비밀번호, 근무 내용은 찍지 않는다. 다만 Pages 로 올리는 파일은 실행마다 아티팩트로 하루 동안 남고, 공개 저장소의 아티팩트는 GitHub 에 로그인한 사람이면 누구나 받을 수 있다. 근무 일정을 남이 보지 않게 하려면 저장소를 비공개로 돌린다. 비공개 저장소에서 Pages 를 쓰려면 GitHub Pro 이상이 필요하다.

## 로컬에서 돌리기

```bash
python -m flex2ics --out out/flex.ics
```

`FLEX_EMAIL`, `FLEX_PASSWORD` 가 없으면 터미널에서 입력받고, 비밀번호는 화면에 보이지 않는다. 받는 기간은 `--past-days`, `--future-days` 로 바꾼다.

```bash
python -m unittest discover -s tests -t .
```

## 참고

로그인 순서와 근무 일정 API 경로는 [planetarium/flex-ax](https://github.com/planetarium/flex-ax) 를 참고했다.
