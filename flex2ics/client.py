"""flex 웹 앱이 쓰는 API 로 로그인하고 내 근무 일정을 받는다.

flex 는 이 용도로 쓸 API 를 구성원에게 열어 두지 않는다. Open API 는 회사가 따로
구독하는 기능이고 토큰도 관리자만 발급한다. 그래서 웹 앱이 브라우저에서 부르는
경로를 그대로 부른다.

로그인은 실행할 때마다 이메일과 비밀번호로 새로 한다. 세션을 저장해 두고 이어
쓰려면 갱신된 토큰을 매번 어딘가에 다시 써 넣어야 하는데, flex 는 회사마다 세션
만료 시간을 정해 두어서 그 고리가 한 번만 끊겨도 사람이 다시 로그인해야 한다.
매번 로그인하면 지켜야 할 상태가 없다.

로그인 순서는 웹 앱과 같다. 로그인 세션을 열고(challenge) 이메일과 비밀번호를
차례로 확인받으면 워크스페이스 토큰이 나온다. 그것을 회사 단위 토큰으로 바꾸면
그 뒤의 API 는 그 토큰을 x-flex-aid 헤더에 실어 부른다.

토큰과 비밀번호, 응답 내용은 어디에도 출력하지 않는다. 실패 메시지에는 단계
이름과 상태 코드만 싣는다. 공개 저장소의 Actions 로그는 누구나 읽을 수 있다.
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://flex.team"
USER_AGENT = "flex2ics (+https://github.com/KENNYSOFT/flex2ics)"
TIMEZONE = "Asia/Seoul"


class FlexError(RuntimeError):
    """flex 호출이 실패했다. 요청과 응답의 본문은 담지 않는다."""

    def __init__(self, step, reason):
        super().__init__("flex %s 실패: %s" % (step, reason))
        self.step = step
        self.reason = reason


def _headers(device_id, extra=None):
    """웹 앱이 모든 호출에 붙이는 헤더를 만든다."""
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
        "flexteam-deviceid": device_id,
        "flexteam-locale": "ko",
        "flexteam-productcode": "FLEX",
        "x-flex-axios": "base",
    }
    if extra:
        headers.update(extra)
    return headers


def _call(step, method, path, headers, body=None, query=None, retries=3, timeout=30):
    """JSON 을 주고받는다. 서버 오류와 요청 과다일 때만 다시 시도한다.

    4xx 는 다시 보내도 같은 답이 온다. 특히 비밀번호가 틀렸을 때 거듭 보내면
    계정이 잠길 수 있으므로 바로 멈춘다.
    """
    url = BASE + path
    if query:
        url += "?" + urllib.parse.urlencode(query)
    data = None if body is None else json.dumps(body).encode("utf-8")
    error = None
    for attempt in range(retries):
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read()
        except urllib.error.HTTPError as exc:
            error = FlexError(step, "HTTP %d" % exc.code)
            if exc.code < 500 and exc.code != 429:
                raise error from None
        except (urllib.error.URLError, TimeoutError) as exc:
            error = FlexError(step, type(exc).__name__)
        else:
            try:
                return json.loads(payload.decode("utf-8"))
            except ValueError:
                raise FlexError(step, "JSON 이 아닌 응답") from None
        if attempt < retries - 1:
            time.sleep(2 * (attempt + 1))
    raise error


class Session:
    """회사 단위 토큰으로 내 근무를 조회한다."""

    def __init__(self, device_id, token, user_id, customer_id):
        self._headers = _headers(device_id, {"x-flex-aid": token})
        self.user_id = user_id
        self.customer_id = customer_id

    def work_forms(self):
        """근무 형태 id 를 화면에 보이는 이름(근무, 재택근무, 외근 같은)으로 바꾸는 표를 준다.

        지난 기록에는 지금은 쓰지 않는 근무 형태가 남아 있을 수 있어 비활성 형태도 받는다.
        """
        data = _call(
            "근무 형태 조회",
            "GET",
            "/api/v2/work-rule/customers/%s/work-forms" % self.customer_id,
            self._headers,
            query={"includeInactive": "true"},
        )
        return {str(form["customerWorkFormId"]): form["display"]["name"] for form in data["workForms"]}

    def work_schedules(self, start, end):
        """start 부터 end 까지(둘 다 포함) 날짜별 근무 일정을 준다."""
        data = _call(
            "근무 일정 조회",
            "GET",
            "/api/v3/time-tracking/users/%s/work-schedules" % self.user_id,
            self._headers,
            query={"from": start.isoformat(), "to": end.isoformat(), "timezone": TIMEZONE},
        )
        return data["dailySchedules"]


def login(email, password, device_id):
    """이메일과 비밀번호로 로그인해 Session 을 준다.

    여러 회사에 속한 계정이면 flex 가 돌려주는 첫 회사를 쓴다.
    """
    base = _headers(device_id)
    challenge = _call(
        "로그인 시작", "POST", "/api-public/v2/auth/challenge", base, body={"loginAuthzFlow": False}
    )
    login_headers = dict(base, **{"flexteam-v2-login-session-id": challenge["sessionId"]})
    _call(
        "이메일 확인",
        "POST",
        "/api-public/v2/auth/verification/identifier",
        login_headers,
        body={"identifier": email},
    )
    _call(
        "비밀번호 확인",
        "POST",
        "/api-public/v2/auth/authentication/password",
        login_headers,
        body={"password": password},
    )
    authorization = _call("토큰 발급", "POST", "/api-public/v2/auth/authorization", login_headers, body={})
    workspace_token = authorization["v2Response"]["workspaceToken"]["accessToken"]["token"]

    workspace_headers = dict(base, **{"flexteam-v2-workspace-access": workspace_token})
    pairs = _call("소속 회사 조회", "GET", "/api-public/v2/auth/tokens/customer-user", workspace_headers)
    if not pairs:
        raise FlexError("소속 회사 조회", "속한 회사가 없다")
    exchanged = _call(
        "회사 토큰 교환",
        "POST",
        "/api-public/v2/auth/tokens/customer-user/exchange",
        workspace_headers,
        body={"customerUuid": pairs[0]["customerUuid"], "userUuid": pairs[0]["userUuid"]},
    )
    token = exchanged["token"]

    me = _call(
        "내 정보 조회",
        "GET",
        "/api/v2/core/users/me/workspace-users-corp-group-affiliates",
        _headers(device_id, {"x-flex-aid": token}),
    )
    current = me.get("currentUser") or me["users"][0]
    return Session(device_id, token, current["user"]["userIdHash"], current["customer"]["customerIdHash"])
