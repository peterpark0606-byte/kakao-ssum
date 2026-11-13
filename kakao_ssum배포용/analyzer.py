"""
analyzer.py — 카톡 대화 파싱 + 분석 로직 (Streamlit 의존성 없음)
"""

import io
import math
import random
import re
from collections import Counter
from datetime import datetime, timedelta

import pandas as pd

# ═════════════════════════════════════════════
# 1. 파싱
# ═════════════════════════════════════════════
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}

# PC: [이름] [오후 3:12] 메시지  /  [Name] [3:12 PM] msg
RE_PC_MSG = re.compile(
    r"^\[(.+?)\] \[(?:(오전|오후|AM|PM) )?(\d{1,2}):(\d{2})(?: (AM|PM))?\] (.*)$")
RE_PC_SEP = re.compile(r"^-{3,}\s*(.+?)\s*-{3,}\s*$")
RE_KO_DATE = re.compile(r"(\d{4})년 (\d{1,2})월 (\d{1,2})일")
RE_EN_DATE = re.compile(r"([A-Za-z]{3,9})\.? (\d{1,2}), (\d{4})")

# 모바일(한국어): 2026년 11월 1일 오후 3:12, 이름 : 메시지  /  2026. 11. 1. 오후 3:12, 이름 : 메시지
RE_MO_KO = re.compile(
    r"^(\d{4})(?:년 |\. ?)(\d{1,2})(?:월 |\. ?)(\d{1,2})(?:일|\.)\s*(오전|오후)?\s*(\d{1,2}):(\d{2}),?\s(.+?) : (.*)$")
# 모바일(영어): Nov 1, 2026 at 3:12 PM, Name : msg   /  November 1, 2026, 3:12 PM, Name : msg
RE_MO_EN = re.compile(
    r"^([A-Za-z]{3,9})\.? (\d{1,2}), (\d{4})(?:,| at)? (\d{1,2}):(\d{2}) ?(AM|PM)?, (.+?) : (.*)$")
RE_MO_STAMP = re.compile(r"^(\d{4})(?:년 |\. ?)(\d{1,2})(?:월 |\. ?)(\d{1,2})(?:일|\.)|^[A-Za-z]{3,9}\.? \d{1,2}, \d{4}")

SYSTEM_HINTS = ("저장한 날짜", "님과 카카오톡 대화", "Talk_", "Date Saved", "님이 들어왔습니다", "님이 나갔습니다",
                "님을 초대했습니다", "채팅방 관리자가")


def _to_24h(ampm, hour):
    hour = int(hour)
    if ampm in ("오후", "PM") and hour != 12:
        hour += 12
    if ampm in ("오전", "AM") and hour == 12:
        hour = 0
    return hour


def _month(name):
    return MONTHS.get(name[:3].lower())


def decode_bytes(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr", "utf-16"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return raw.decode("utf-8", errors="ignore")


def parse_csv(text: str) -> pd.DataFrame:
    df = pd.read_csv(io.StringIO(text))
    cols = {c.strip().lower(): c for c in df.columns}
    need = ["date", "user", "message"]
    if not all(k in cols for k in need):
        raise ValueError("CSV 열 이름이 Date, User, Message 형식이 아니에요.")
    df = df.rename(columns={cols["date"]: "time", cols["user"]: "sender", cols["message"]: "message"})
    df["time"] = pd.to_datetime(df["time"], errors="coerce")
    return df[["time", "sender", "message"]]


def parse_txt(text: str) -> pd.DataFrame:
    rows, cur_date = [], None
    for line in text.splitlines():
        line = line.rstrip("\r")
        if not line.strip():
            continue

        m = RE_PC_SEP.match(line)
        if m:
            inner = m.group(1)
            k = RE_KO_DATE.search(inner)
            e = RE_EN_DATE.search(inner)
            if k:
                cur_date = tuple(map(int, k.groups()))
            elif e and _month(e.group(1)):
                cur_date = (int(e.group(3)), _month(e.group(1)), int(e.group(2)))
            continue

        m = RE_PC_MSG.match(line)
        if m and cur_date:
            sender, ap1, h, mi, ap2, msg = m.groups()
            try:
                rows.append([datetime(*cur_date, _to_24h(ap1 or ap2, h), int(mi)), sender, msg])
            except ValueError:
                pass
            continue

        m = RE_MO_KO.match(line)
        if m:
            y, mo, d, ap, h, mi, sender, msg = m.groups()
            try:
                rows.append([datetime(int(y), int(mo), int(d), _to_24h(ap, h), int(mi)), sender, msg])
            except ValueError:
                pass
            continue

        m = RE_MO_EN.match(line)
        if m and _month(m.group(1)):
            mon, d, y, h, mi, ap, sender, msg = m.groups()
            try:
                rows.append([datetime(int(y), _month(mon), int(d), _to_24h(ap, h), int(mi)), sender, msg])
            except ValueError:
                pass
            continue

        if RE_MO_STAMP.match(line) or any(s in line for s in SYSTEM_HINTS):
            continue

        if rows:  # 여러 줄 메시지
            rows[-1][2] += "\n" + line

    return pd.DataFrame(rows, columns=["time", "sender", "message"])


def room_name(raw: bytes) -> str:
    """내보내기 첫 줄('OOO 님과 카카오톡 대화')에서 방 이름 추출"""
    head = decode_bytes(raw).splitlines()[:3]
    for line in head[:3]:
        m = re.match(r"^\s*(.+?)\s*(?:\d+\s*)?님과 카카오톡 대화", line)
        if m:
            return m.group(1).strip()
    return ""


def parse_kakao(raw: bytes, filename: str) -> pd.DataFrame:
    text = decode_bytes(raw)
    df = parse_csv(text) if filename.lower().endswith(".csv") else parse_txt(text)
    df = df.dropna(subset=["time", "sender"])
    df["sender"] = df["sender"].astype(str).str.strip()
    df["message"] = df["message"].fillna("").astype(str)
    return df.sort_values("time", kind="stable").reset_index(drop=True)


# ═════════════════════════════════════════════
# 2. 개인정보 보호
# ═════════════════════════════════════════════
ALIASES = ["하트", "별", "구름", "달", "토끼", "곰", "고양이", "강아지", "여우", "펭귄", "판다", "햄찌"]
RE_PHONE = re.compile(r"01[016789][-\s.]?\d{3,4}[-\s.]?\d{4}")
RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
RE_LONGNUM = re.compile(r"\d{6,}[-\d]*")
RE_URL = re.compile(r"https?://\S+")


def short_name(name: str) -> str:
    """'박영우(아시아경제)' → '박영우' (괄호 속 소속 제거, 화면 표시용)"""
    s = re.sub(r"\s*[\(\[（【].*?[\)\]）】]\s*", "", str(name)).strip()
    return s or str(name)


def mask_text(s: pd.Series) -> pd.Series:
    return (s.str.replace(RE_URL, "[링크]", regex=True)
             .str.replace(RE_PHONE, "[전화번호]", regex=True)
             .str.replace(RE_EMAIL, "[이메일]", regex=True)
             .str.replace(RE_LONGNUM, "[숫자]", regex=True))


def anonymize(df: pd.DataFrame, rename: bool) -> tuple[pd.DataFrame, dict]:
    df = df.copy()
    df["message"] = mask_text(df["message"])
    mapping = {}
    if rename:
        order = df["sender"].value_counts().index
        for i, name in enumerate(order):
            mapping[name] = ALIASES[i] if i < len(ALIASES) else f"참여자{i + 1}"
        df["sender"] = df["sender"].map(mapping)
    return df, mapping


# ═════════════════════════════════════════════
# 3. 샘플 대화
# ═════════════════════════════════════════════
def make_sample(me="민준", you="지은") -> str:
    rnd = random.Random(1004)
    opener_me = ["뭐해??", "점심 먹었어?", "오늘 날씨 미쳤다 ㅋㅋ", "퇴근했어?", "이거 봐봐 ㅋㅋㅋㅋ", "자니..?"]
    opener_you = ["뭐해", "나 방금 웃긴거 봄 ㅋㅋ", "점심 뭐먹었어?", "오늘 좀 피곤하다 ㅠ"]
    talk_me = ["ㅋㅋㅋㅋㅋㅋ 진짜?", "헐 대박", "나도 그거 좋아해!!", "주말에 뭐해?", "이모티콘",
               "그럼 다음에 같이 가자 ㅎㅎ", "오 완전 좋다", "사진", "ㅋㅋㅋ 너 진짜 웃기다",
               "피곤하겠다 ㅠㅠ 얼른 쉬어", "보고싶다..는 농담 ㅋㅋ", "내일 뭐해??", "영화 좋아해?"]
    talk_you = ["ㅋㅋㅋ 응", "그치", "ㅋㅋㅋㅋ 아 진짜?", "나 그거 아직 안봤어", "좋아 ㅎㅎ", "이모티콘",
                "음 생각해볼게 ㅋㅋ", "오 맛있겠다", "너는?", "ㅎㅎ 고마워", "사진", "헐 ㅋㅋㅋㅋ"]
    talk_you_late = ["나도 보고싶다 ㅎㅎ", "내일 만날래?", "ㅋㅋㅋ 너랑 얘기하면 재밌어", "오늘 뭐했어?"]
    weekdays = "월화수목금토일"
    start = datetime(2026, 10, 20)
    lines = [f"{you} 님과 카카오톡 대화", "저장한 날짜 : 2026-11-12 23:59:00", ""]

    def fmt(t, who, msg):
        ampm = "오전" if t.hour < 12 else "오후"
        return f"[{who}] [{ampm} {t.hour % 12 or 12}:{t.minute:02d}] {msg}"

    last_date = None
    for day in range(24):
        d = start + timedelta(days=day)
        warmth = 0.4 + day / 40
        hours = sorted(rnd.sample(range(9, 24), rnd.choice([1, 1, 2, 2, 3])))
        for hr in hours:
            t = d.replace(hour=hr, minute=rnd.randint(0, 50))
            if t.date() != last_date:
                lines.append(f"--------------- {t.year}년 {t.month}월 {t.day}일 {weekdays[t.weekday()]}요일 ---------------")
                last_date = t.date()
            starter = me if rnd.random() < (0.75 - day / 60) else you
            lines.append(fmt(t, starter, rnd.choice(opener_me if starter == me else opener_you)))
            who = starter
            for _ in range(rnd.randint(6, 22 + day)):
                who = you if who == me else me
                if who == you:
                    gap = rnd.choice([1, 2, 3, 5, 8, 15, 30]) / (warmth + 0.3)
                    if day == 5 and rnd.random() < 0.1:
                        gap = 190  # 읽씹 명장면
                else:
                    gap = rnd.choice([0, 1, 1, 2, 3])
                t += timedelta(minutes=gap)
                if t.date() != last_date:
                    lines.append(f"--------------- {t.year}년 {t.month}월 {t.day}일 {weekdays[t.weekday()]}요일 ---------------")
                    last_date = t.date()
                pool = talk_me if who == me else (talk_you + talk_you_late * (day > 14))
                lines.append(fmt(t, who, rnd.choice(pool)))
                if who == me and rnd.random() < 0.35:
                    t += timedelta(minutes=rnd.randint(0, 1))
                    lines.append(fmt(t, who, rnd.choice(pool)))
        if day > 12 and rnd.random() < 0.45:
            t = (d + timedelta(days=1)).replace(hour=0, minute=rnd.randint(5, 40))
            lines.append(f"--------------- {t.year}년 {t.month}월 {t.day}일 {weekdays[t.weekday()]}요일 ---------------")
            last_date = t.date()
            for i, (w, msg) in enumerate([(you, "안자?"), (me, "아직 ㅋㅋ 너는 왜 안자"),
                                          (you, "그냥 ㅎㅎ 잠이 안오네"), (me, "나도.. 무슨 생각해?"),
                                          (you, "비밀 ㅋㅋㅋ")]):
                lines.append(fmt(t + timedelta(minutes=i * 2), w, msg))
    return "\n".join(lines)


def make_group_sample() -> str:
    rnd = random.Random(77)
    people = ["민준", "지은", "현우", "수빈", "도윤"]
    talk = ["ㅋㅋㅋㅋㅋ", "아 진짜?", "나 오늘 과제 망함", "이모티콘", "밥 뭐먹지", "ㅇㅇ", "사진", "헐",
            "누구 내일 수업 감?", "ㅋㅋㅋ 개웃기네", "배고프다", "오 나도", "그거 언제까지임?"]
    pair_talk = ["ㅋㅋㅋ 너 진짜 웃기다", "나도 그거 좋아해!", "같이 가자 ㅎㅎ", "오 너도?"]
    weekdays = "월화수목금토일"
    lines = ["KDT 동기방 님과 카카오톡 대화", ""]
    start = datetime(2026, 10, 25)
    for day in range(18):
        d = start + timedelta(days=day)
        lines.append(f"--------------- {d.year}년 {d.month}월 {d.day}일 {weekdays[d.weekday()]}요일 ---------------")
        t = d.replace(hour=rnd.randint(10, 15), minute=rnd.randint(0, 59))
        prev = None
        for _ in range(rnd.randint(25, 60)):
            if prev == "민준" and rnd.random() < 0.55:
                who, msg = "지은", rnd.choice(pair_talk)
            elif prev == "지은" and rnd.random() < 0.5:
                who, msg = "민준", rnd.choice(pair_talk)
            else:
                who = rnd.choices(people, weights=[5, 4, 6, 2, 1])[0]
                msg = rnd.choice(talk)
            t += timedelta(minutes=rnd.choice([0, 1, 1, 2, 4, 9]))
            if t.date() != d.date():
                break
            ampm = "오전" if t.hour < 12 else "오후"
            lines.append(f"[{who}] [{ampm} {t.hour % 12 or 12}:{t.minute:02d}] {msg}")
            prev = who
    return "\n".join(lines)


# ═════════════════════════════════════════════
# 4. 공통 전처리
# ═════════════════════════════════════════════
STOPWORDS = {"이모티콘", "사진", "동영상", "파일", "삭제된", "메시지입니다", "그냥", "진짜", "근데", "나도",
             "너도", "그래", "그럼", "이제", "아니", "너는", "나는", "링크", "전화번호", "이메일", "숫자",
             "샵검색", "보이스톡", "페이스톡", "해요", "그거", "이거", "저거", "있어", "없어", "하고"}
RE_HEART = r"❤|♥|💕|💖|💗|😍|🥰|😘|보고싶|보고 싶|좋아해|사랑해|설레"


def enrich(df: pd.DataFrame, new_conv_hours: float = 6) -> pd.DataFrame:
    df = df.copy().reset_index(drop=True)
    df["gap_min"] = df["time"].diff().dt.total_seconds() / 60
    df["prev_sender"] = df["sender"].shift()
    df["next_sender"] = df["sender"].shift(-1)
    df["is_opener"] = df["gap_min"].isna() | (df["gap_min"] >= new_conv_hours * 60)
    df["session"] = df["is_opener"].cumsum()
    df["is_closer"] = df["is_opener"].shift(-1, fill_value=True)
    df["is_reply"] = (df["sender"] != df["prev_sender"]) & ~df["is_opener"] & df["prev_sender"].notna()
    df["is_combo"] = (df["sender"] == df["prev_sender"]) & (df["gap_min"] <= 2)
    df["hour"] = df["time"].dt.hour
    df["date"] = df["time"].dt.date
    msg = df["message"]
    df["len"] = msg.str.len()
    df["kk"] = msg.str.count("ㅋ")
    df["question"] = msg.str.contains(r"\?|뭐해|어때|할래|어디야|언제", regex=True).astype(int)
    df["emoticon"] = msg.str.contains("이모티콘").astype(int)
    df["photo"] = msg.str.match(r"^(사진|동영상)").astype(int)
    df["heart"] = msg.str.count(RE_HEART)
    df["dawn"] = df["hour"].between(0, 4).astype(int)
    return df


def _share(x, y):
    x, y = max(x, 0), max(y, 0)
    return 0.5 if x + y == 0 else x / (x + y)


def _median_reply(d, max_hours=6):
    r = d.loc[d["is_reply"] & (d["gap_min"] <= max_hours * 60), "gap_min"]
    return float(r.median()) if len(r) else float("nan")


def person_stats(df: pd.DataFrame, p: str) -> dict:
    d = df[df["sender"] == p]
    n = max(len(d), 1)
    return {
        "메시지 수": len(d),
        "선톡 횟수": int(d["is_opener"].sum()),
        "답장 속도(분, 중앙값)": _median_reply(d),
        "평균 글자 수": float(d["len"].mean()) if len(d) else 0.0,
        "ㅋ 개수": int(d["kk"].sum()),
        "ㅋ/메시지": float(d["kk"].sum() / n),
        "질문 비율": float(d["question"].sum() / n),
        "이모티콘/사진": int(d["emoticon"].sum() + d["photo"].sum()),
        "애정 표현": int(d["heart"].sum()),
        "새벽 메시지": int(d["dawn"].sum()),
        "연타 비율": float(d["is_combo"].sum() / n),
        "마지막 말 횟수": int(d["is_closer"].sum()),
        "_emo_rate": float((d["emoticon"].sum() + d["photo"].sum() + d["heart"].sum() * 3) / n),
    }


WEIGHTS = {"선톡": 25, "답장 속도": 20, "메시지 양": 15, "글 길이": 10, "질문": 10, "ㅋㅋ": 10, "이모티콘·애정": 10}


def heart_share(sa: dict, sb: dict) -> tuple[float, dict]:
    """a의 '마음의 지분'(0~100)과 항목별 a 비율"""
    ra = sa["답장 속도(분, 중앙값)"]
    rb = sb["답장 속도(분, 중앙값)"]
    ra = 30 if math.isnan(ra) else ra
    rb = 30 if math.isnan(rb) else rb
    parts = {
        "선톡": _share(sa["선톡 횟수"], sb["선톡 횟수"]),
        "답장 속도": _share(rb + 0.5, ra + 0.5),
        "메시지 양": _share(sa["메시지 수"], sb["메시지 수"]),
        "글 길이": _share(sa["평균 글자 수"], sb["평균 글자 수"]),
        "질문": _share(sa["질문 비율"], sb["질문 비율"]),
        "ㅋㅋ": _share(sa["ㅋ/메시지"], sb["ㅋ/메시지"]),
        "이모티콘·애정": _share(sa["_emo_rate"], sb["_emo_rate"]),
    }
    return sum(WEIGHTS[k] * v for k, v in parts.items()), parts


def temperature(df: pd.DataFrame) -> dict:
    days_active = df["date"].nunique()
    mpd = len(df) / max(days_active, 1)
    med = _median_reply(df)
    med = 60 if math.isnan(med) else med
    dawn_ratio = df["dawn"].mean()
    last = df["time"].max()
    recent = int((df["time"] > last - timedelta(days=7)).sum())
    prev = int(((df["time"] <= last - timedelta(days=7)) & (df["time"] > last - timedelta(days=14))).sum())
    trend = (recent - prev) / max(recent, prev, 1)
    heart_rate = df["heart"].sum() / max(len(df), 1)
    temp = (30 * min(1, mpd / 80)
            + 25 * max(0, 1 - math.log10(1 + med) / math.log10(1 + 240))
            + 15 * min(1, dawn_ratio / 0.08)
            + 15 * (0.5 + trend / 2)
            + 15 * min(1, heart_rate / 0.03))
    return {"temp": temp, "mpd": mpd, "med_reply": med, "trend": trend, "recent": recent, "prev": prev,
            "days_active": days_active}


# ═════════════════════════════════════════════
# 5. 1:1 분석
# ═════════════════════════════════════════════
def verdict(temp, score_a, a, b):
    diff = score_a - 50
    hot = temp >= 55
    lead, follow = (a, b) if diff > 0 else (b, a)
    if hot and abs(diff) < 7:
        return "💞", "쌍방 썸 확정", "둘 다 진심이에요. 고백 타이밍은 지금입니다."
    if hot:
        return "🔥", "한쪽이 더 달아오름", f"{lead}님이 더 좋아하는 중. {follow}님도 싫진 않은 듯?"
    if abs(diff) < 7:
        return "🧊", "미지근한 친구 사이", "대화는 고르지만 설렘 온도가 낮아요. 분위기 전환이 필요!"
    return "💔", "짝사랑 경보", f"{lead}님 혼자 열심히 달리는 중... {follow}님 반응을 다시 보세요."


def badges(s: dict, other: dict) -> list[tuple[str, str, str]]:
    out = []
    r = s["답장 속도(분, 중앙값)"]
    total_open = s["선톡 횟수"] + other["선톡 횟수"]
    total_close = s["마지막 말 횟수"] + other["마지막 말 횟수"]
    if not math.isnan(r) and r < 2:
        out.append(("⚡", "칼답 장인", f"보통 {r:.0f}분 안에 답장"))
    if not math.isnan(r) and r >= 20:
        out.append(("🐢", "느긋한 거북이", f"답장까지 평균 {r:.0f}분"))
    if total_open and s["선톡 횟수"] / total_open >= 0.6:
        out.append(("🧚", "선톡 요정", f"대화 시작의 {s['선톡 횟수'] / total_open:.0%} 담당"))
    if s["ㅋ/메시지"] >= 1.0:
        out.append(("😂", "ㅋ 무한 생성기", f"ㅋ {s['ㅋ 개수']:,}개 생산"))
    if s["새벽 메시지"] >= 10:
        out.append(("🌙", "새벽 감성러", f"새벽 메시지 {s['새벽 메시지']}개"))
    if s["질문 비율"] >= 0.25:
        out.append(("❓", "질문 폭격기", f"메시지의 {s['질문 비율']:.0%}가 질문"))
    if s["평균 글자 수"] >= 18:
        out.append(("📜", "장문 작가", f"평균 {s['평균 글자 수']:.0f}자"))
    if 0 < s["평균 글자 수"] < 6:
        out.append(("🤐", "단답 마스터", f"평균 {s['평균 글자 수']:.1f}자"))
    if s["메시지 수"] and s["이모티콘/사진"] / s["메시지 수"] >= 0.12:
        out.append(("🎨", "이모티콘 부자", f"이모티콘·사진 {s['이모티콘/사진']}개"))
    if s["연타 비율"] >= 0.35:
        out.append(("🥊", "연타 장인", f"{s['연타 비율']:.0%}가 연속 메시지"))
    if s["애정 표현"] >= 5:
        out.append(("💘", "애정 표현 장인", f"하트·보고싶어 {s['애정 표현']}회"))
    if total_close and s["마지막 말 횟수"] / total_close >= 0.65:
        out.append(("🔚", "마지막 말 담당", "대화가 주로 이 사람 말로 끝나요"))
    if not out:
        out.append(("🕊️", "평화주의자", "모든 지표가 무난무난"))
    return out


def timeline(df: pd.DataFrame, a: str, b: str) -> pd.DataFrame:
    df = df.copy()
    df["week"] = df["time"].dt.to_period("W-SUN").dt.start_time
    rows = []
    for w, g in df.groupby("week"):
        if len(g) < 10 or g["sender"].nunique() < 2:
            continue
        sa, sb = person_stats(g, a), person_stats(g, b)
        score_a, _ = heart_share(sa, sb)
        rows.append({"주": w, f"{a}": score_a, f"{b}": 100 - score_a, "메시지": len(g),
                     "답장(분)": _median_reply(g)})
    return pd.DataFrame(rows)


def _clip(s, n=28):
    s = str(s).replace("\n", " ")
    return s if len(s) <= n else s[:n] + "…"


def _dur(minutes):
    minutes = int(round(minutes))
    if minutes < 60:
        return f"{minutes}분"
    h, m = divmod(minutes, 60)
    if h < 24:
        return f"{h}시간 {m}분" if m else f"{h}시간"
    d, h = divmod(h, 24)
    return f"{d}일 {h}시간"


def highlights(df: pd.DataFrame, a: str, b: str) -> list[tuple[str, str, str]]:
    out = []
    first, last = df["time"].min(), df["time"].max()
    out.append(("📆", "함께한 기록",
                f"{first:%Y.%m.%d} ~ {last:%Y.%m.%d} · {(last.date() - first.date()).days + 1}일 중 {df['date'].nunique()}일 대화, "
                f"총 {len(df):,}개 메시지"))

    sess = df.groupby("session").agg(n=("message", "size"), start=("time", "min"), end=("time", "max"))
    if len(sess):
        s = sess.sort_values("n", ascending=False).iloc[0]
        out.append(("🔥", "역대급 수다",
                    f"{s['start']:%m월 %d일 %H:%M}부터 {_dur((s['end'] - s['start']).total_seconds() / 60)} 동안 "
                    f"메시지 {s['n']}개를 주고받았어요"))

    day = df.groupby("date").size()
    out.append(("🏆", "가장 불타오른 날", f"{day.idxmax():%m월 %d일} — 하루 {day.max()}개"))

    for p in (a, b):
        d = df[(df["sender"] == p) & (df["sender"] != df["prev_sender"]) & df["prev_sender"].notna()
               & (df["gap_min"] >= 30) & (df["gap_min"] <= 60 * 24 * 3)]
        if len(d):
            row = d.loc[d["gap_min"].idxmax()]
            prev_msg = df.loc[row.name - 1, "message"]
            out.append(("🫥", f"{p}님의 최장 읽씹",
                        f"“{_clip(prev_msg)}”에 {_dur(row['gap_min'])} 만에 답장 ({row['time']:%m/%d})"))

    for p in (a, b):
        d = df[(df["sender"] == p) & df["message"].str.contains(r"보고싶|보고 싶|좋아해|사랑해|설레", regex=True)]
        if len(d):
            row = d.iloc[0]
            out.append(("💌", f"{p}님의 첫 고백성 멘트", f"{row['time']:%m월 %d일 %H:%M} — “{_clip(row['message'])}”"))

    dawn = df[df["dawn"] == 1]
    if len(dawn):
        row = dawn.iloc[0]
        out.append(("🌙", "첫 새벽 대화", f"{row['time']:%m월 %d일 %H:%M}, {row['sender']}님이 먼저 — “{_clip(row['message'])}”"))
    return out


def top_words(df: pd.DataFrame, p: str, n=12):
    tokens = re.findall(r"[가-힣a-zA-Z]{2,}", " ".join(df.loc[df["sender"] == p, "message"]))
    return Counter(t for t in tokens if t not in STOPWORDS).most_common(n)


def tips(sa, sb, a, b, trend):
    t = []
    if sb["선톡 횟수"] > sa["선톡 횟수"]:
        t.append(f"✅ {b}님이 선톡을 더 많이 해요. 먼저 생각난다는 뜻!")
    else:
        t.append(f"🤔 선톡은 주로 {a}님 몫. 하루쯤 참아보면 {b}님 반응을 볼 수 있어요.")
    rb = sb["답장 속도(분, 중앙값)"]
    if not math.isnan(rb):
        t.append(f"⚡ {b}님 답장이 매우 빨라요. 폰을 손에서 안 놓는 중일지도?" if rb < 3
                 else f"⏳ {b}님은 답장이 느긋한 편({rb:.0f}분). 바쁜 건지 밀당인지는 지켜보세요.")
    if sb["질문 비율"] > sa["질문 비율"]:
        t.append(f"❓ {b}님이 질문을 더 많이 해요. 궁금하다는 건 관심 있다는 것.")
    else:
        t.append(f"❓ {b}님 질문이 적은 편. 대화를 이어갈 '떡밥'을 더 던져보세요.")
    if sb["애정 표현"] > 0:
        t.append(f"💗 {b}님의 애정 표현 {sb['애정 표현']}회 포착!")
    if trend > 0.1:
        t.append("📈 최근 대화량이 늘고 있어요. 흐름 좋습니다!")
    elif trend < -0.1:
        t.append("📉 최근 대화량이 줄었어요. 새 주제나 약속 제안으로 불씨를 살려보세요.")
    return t


# ─── 썸 MBTI(유형) ───
def person_type(s: dict, other: dict) -> tuple[str, str]:
    """(유형 이름, 한 줄 설명)"""
    tot = s["선톡 횟수"] + other["선톡 횟수"]
    share = s["선톡 횟수"] / tot if tot else 0.5
    if share >= 0.56:
        tail, tail_d = "직진러", "먼저 다가가는 타입"
    elif share <= 0.44:
        tail, tail_d = "츤데레", "먼저 연락은 안 해도 오면 반기는 타입"
    else:
        tail, tail_d = "밀당러", "주고받는 균형을 아는 타입"
    r = s["답장 속도(분, 중앙값)"]
    n = max(s["메시지 수"], 1)
    traits = [
        (s["새벽 메시지"] / n >= 0.08, "새벽감성", "밤이 깊을수록 말이 많아지고"),
        (not math.isnan(r) and r < 1.5, "칼답", "알림 뜨자마자 답하고"),
        (s["ㅋ/메시지"] >= 1.2, "ㅋㅋ폭격", "리액션이 늘 빵빵하고"),
        (s["질문 비율"] >= 0.25, "궁금증폭발", "질문으로 대화를 이어가고"),
        (s["애정 표현"] >= 8, "꿀떨어지는", "애정 표현을 아끼지 않고"),
        (s["평균 글자 수"] >= 18, "장문러", "한 번 말하면 길게 하고"),
        (s["이모티콘/사진"] / n >= 0.12, "이모티콘", "말보다 이모티콘이 빠르고"),
        (0 < s["평균 글자 수"] < 6, "단답", "짧고 굵게 말하고"),
        (not math.isnan(r) and r >= 20, "느긋", "답장은 느려도 꾸준하고"),
    ]
    for ok, name, d in traits:
        if ok:
            return f"{name} {tail}", f"{d}, {tail_d}"
    return f"무난 {tail}", f"모든 게 평균이고, {tail_d}"


COUPLE_NAMES = {
    "💞": ("자석 커플", "서로 끌어당기는 중"),
    "🔥": ("불꽃 × 성냥 커플", "한쪽은 활활, 한쪽은 이제 막 불붙는 중"),
    "🧊": ("적금 커플", "천천히, 꾸준히 쌓이는 중"),
    "💔": ("해바라기 커플", "한 사람만 바라보는 중"),
}

DAYS = "월화수목금토일"


def _hour_txt(h):
    part = "새벽" if h < 5 else ("오전" if h < 12 else ("오후" if h < 18 else "밤"))
    return f"{part} {h % 12 or 12}시"


def confession(df: pd.DataFrame, temp, score_a, trend, b, today=None):
    """고백 성공 확률(%)과 추천 타이밍"""
    balance = 100 - 2 * abs(score_a - 50)
    p = 0.55 * temp + 0.30 * balance + 15 * (0.5 + trend / 2)
    p = max(5, min(97, p))
    if p >= 80:
        label = "지금 바로 GO! 🚀"
    elif p >= 60:
        label = "분위기만 조금 더 띄우면 성공각 ✨"
    elif p >= 40:
        label = "아직은 이르다. 2주만 더 쌓자 ⏳"
    else:
        label = "고백보다 친해지기가 먼저 🌱"
    d = df[df["sender"] == b]
    d = d if len(d) >= 10 else df
    wd = int(d["time"].dt.weekday.value_counts().idxmax())
    hr = int(d["hour"].value_counts().idxmax())
    today = today or datetime.now()
    ahead = (wd - today.weekday()) % 7
    if ahead == 0 and today.hour >= hr:
        ahead = 7
    day = today + timedelta(days=ahead)
    when = f"{DAYS[wd]}요일 {_hour_txt(hr)}"
    dday = "D-DAY 오늘!" if ahead == 0 else f"D-{ahead} ({day:%m/%d} {DAYS[wd]})"
    why = f"{b}님이 가장 활발하게 답하는 요일·시간대예요"
    return {"prob": p, "label": label, "when": when, "dday": dday, "why": why}


def analyze_pair(df_all: pd.DataFrame, a: str, b: str, new_conv_hours=6) -> dict:
    df = enrich(df_all[df_all["sender"].isin([a, b])], new_conv_hours)
    sa, sb = person_stats(df, a), person_stats(df, b)
    score_a, parts = heart_share(sa, sb)
    T = temperature(df)
    emoji, title, desc = verdict(T["temp"], score_a, a, b)
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("Asia/Seoul")).replace(tzinfo=None)
    except Exception:  # noqa: BLE001
        now = datetime.now()
    return {
        "types": {a: person_type(sa, sb), b: person_type(sb, sa)},
        "couple": COUPLE_NAMES[emoji],
        "confess": confession(df, T["temp"], score_a, T["trend"], b, now),
        "df": df, "stats": {a: sa, b: sb}, "score_a": score_a, "parts": parts, **T,
        "emoji": emoji, "title": title, "desc": desc,
        "badges": {a: badges(sa, sb), b: badges(sb, sa)},
        "timeline": timeline(df, a, b), "highlights": highlights(df, a, b),
        "words": {a: top_words(df, a), b: top_words(df, b)},
        "tips": tips(sa, sb, a, b, T["trend"]),
    }


# ═════════════════════════════════════════════
# 6. 단톡방 분석
# ═════════════════════════════════════════════
def analyze_group(df_all: pd.DataFrame, min_msgs=5, reply_window_min=10, new_conv_hours=3) -> dict:
    counts = df_all["sender"].value_counts()
    members = counts[counts >= min_msgs].index.tolist()
    df = enrich(df_all[df_all["sender"].isin(members)], new_conv_hours)

    rank = pd.DataFrame({p: {
        "메시지": int((df["sender"] == p).sum()),
        "선톡": int(df.loc[df["sender"] == p, "is_opener"].sum()),
        "답장 속도(분)": _median_reply(df[df["sender"] == p], 1),
        "ㅋ/메시지": df.loc[df["sender"] == p, "kk"].mean(),
        "허공 외침": int((df["sender"] == p).mul(df["is_closer"]).sum()),
    } for p in members}).T

    rep = df[df["is_reply"] & (df["gap_min"] <= reply_window_min)]
    mat = pd.crosstab(rep["sender"], rep["prev_sender"]).reindex(index=members, columns=members, fill_value=0)

    # 쌍별 '케미' : 서로에게 답한 횟수를 두 사람 메시지 수로 정규화
    pairs = []
    for i, x in enumerate(members):
        for y in members[i + 1:]:
            mutual = mat.loc[x, y] + mat.loc[y, x]
            base = counts[x] + counts[y]
            fast = rep[((rep["sender"] == x) & (rep["prev_sender"] == y)) |
                       ((rep["sender"] == y) & (rep["prev_sender"] == x))]["gap_min"]
            pairs.append({"커플": f"{x} ♥ {y}", "a": x, "b": y, "주고받은 답장": int(mutual),
                          "케미 지수": 100 * mutual / max(base, 1),
                          "평균 답장(분)": float(fast.mean()) if len(fast) else float("nan")})
    pairs = pd.DataFrame(pairs).sort_values("케미 지수", ascending=False).reset_index(drop=True)

    awards = []
    if len(rank):
        awards.append(("🗣️", "수다왕", rank["메시지"].idxmax(), f"메시지 {int(rank['메시지'].max()):,}개"))
        awards.append(("🧚", "선톡왕", rank["선톡"].idxmax(), f"대화 시작 {int(rank['선톡'].max())}회"))
        rr = rank["답장 속도(분)"].dropna()
        if len(rr):
            awards.append(("⚡", "칼답왕", rr.idxmin(), f"평균 {rr.min():.1f}분"))
        awards.append(("😂", "리액션왕", rank["ㅋ/메시지"].idxmax(), f"메시지당 ㅋ {rank['ㅋ/메시지'].max():.1f}개"))
        closer_rate = rank["허공 외침"] / rank["메시지"].clip(lower=1)
        awards.append(("📢", "허공에 외치는 자", closer_rate.idxmax(), "이 사람 말로 대화가 끊긴 비율 1위"))
    return {"df": df, "members": members, "rank": rank, "matrix": mat, "pairs": pairs, "awards": awards}


# ═════════════════════════════════════════════
# 7. 팀플 모드
# ═════════════════════════════════════════════
RE_WORK = (r"자료|파일|링크|ppt|PPT|피피티|발표|보고서|대본|슬라이드|코드|깃|github|노션|구글|드라이브|"
           r"조사|정리|초안|수정|피드백|역할|분담|마감|제출|회의|일정|파트|레퍼런스|설문|데이터|분석|"
           r"\[링크\]|\.pptx|\.pdf|\.docx|\.hwp|\.xlsx|\.zip")
RE_LEAD = (r"회의|모이자|모일까|모입시다|줌 |zoom|Zoom|역할|분담|정리해서|해주세요|해 주세요|맡아|일정 |투표|공지|"
           r"각자|마감이|까지 (?:해|올려|제출|완성|마감)|다들 [^ㅋ?]*(?:가능|해주|공유|확인|올려)")
RE_DONE = r"완료|했어요|했습니다|했어|올렸|업로드|끝냈|다했|다 했|수정했|반영했|보냈|공유했|작성했|만들었"
RE_FILE = r"^(?:사진|동영상)|파일[:：]|\[링크\]|\.pptx|\.pdf|\.docx|\.hwp|\.xlsx|\.zip"
RE_YES = r"^\s*(?:넵|네|넹|녜|ㅇㅋ|ㅇㅇ|오키|오케이|okay|ok|OK|알겠습니다|알겠어요|확인|확인했습니다|넵넵|좋아요|좋습니다|굿|ㄱㄱ|ㅇㅋㅇㅋ)[!.~ㅎㅋ\s]*$"

TEAM_WEIGHTS = {"업무 대화": 25, "완료 보고": 20, "자료 공유": 20, "주도(회의·분담)": 20, "호출 응답률": 15}

ROLES = {
    "lead": ("🧭", "팀장", "회의 잡고 일 나누는 사람"),
    "file": ("📁", "자료 담당", "파일·링크를 제일 많이 올림"),
    "done": ("🛠️", "실무 일꾼", "'했어요' 보고가 제일 많음"),
    "kk": ("🎉", "분위기 메이커", "팀플 지옥에 웃음을 담당"),
    "ask": ("🙋", "질문 요정", "모르는 건 바로 물어봄"),
    "yes": ("🙇", "'넵' 봇", "대답은 잘함. 대답만."),
    "fast": ("⚡", "칼답러", "부르면 1분 안에 나타남"),
    "night": ("🌙", "야근러", "밤 11시 이후 업무 대화 담당"),
}


def make_team_sample() -> str:
    rnd = random.Random(2026)
    weekdays = "월화수목금토일"
    T = {
        "승욱": ["다들 내일 9시 줌 회의 가능?", "역할 분담 정리해서 노션에 올릴게요", "발표 자료 금요일까지 마감이에요!",
                "각자 파트 진행상황 공유해주세요", "피드백 반영해서 최종본 정리했어요", "그럼 자료조사는 지민님이 맡아주세요"],
        "지민": ["자료 찾아서 드라이브에 올렸어요", "파일: 레퍼런스_정리.pdf", "https://drive.google.com/abc", "사진",
                "이 논문 참고하면 좋을 것 같아요 https://scholar.google.com", "ppt 초안 공유했습니다"],
        "수아": ["제 파트 슬라이드 다 했어요", "수정했습니다!", "데이터 분석 결과 정리했어요", "대본 초안 작성했어요",
                "혹시 3번 슬라이드 순서 바꿔도 될까요?", "피드백 반영했어요"],
        "현우": ["넵", "네!", "넵넵", "확인했습니다", "ㅇㅋ", "좋아요", "저는 아무거나 괜찮아요"],
        "태호": ["ㅋㅋㅋㅋㅋㅋ 살려줘", "팀플 끝나면 고기 먹으러 가요 ㅋㅋ", "이모티콘", "다들 화이팅 ㅋㅋㅋ",
                "제 파트 내일까지 할게요 ㅠㅠ", "아 맞다 그거 언제까지였죠?"],
    }
    weight = {"승욱": 5, "지민": 4, "수아": 4, "현우": 2, "태호": 3}
    lines = ["의료기기 RA 팀플 4조 님과 카카오톡 대화", ""]
    start = datetime(2026, 10, 19)
    for day in range(21):
        d = start + timedelta(days=day)
        crunch = day >= 17
        n_sess = 3 if crunch else rnd.choice([0, 1, 1, 2])
        if n_sess == 0:
            continue
        lines.append(f"--------------- {d.year}년 {d.month}월 {d.day}일 {weekdays[d.weekday()]}요일 ---------------")
        hours = sorted(rnd.sample(range(10, 23), n_sess))
        if crunch:
            hours[-1] = 23
        for hr in hours:
            t = d.replace(hour=hr, minute=rnd.randint(0, 30))
            seq = ["승욱"] + rnd.choices(list(weight), weights=list(weight.values()), k=rnd.randint(8, 26 if crunch else 14))
            for who in seq:
                t += timedelta(minutes=rnd.choice([0, 1, 1, 2, 3, 6]))
                if t.date() != d.date():
                    break
                ampm = "오전" if t.hour < 12 else "오후"
                lines.append(f"[{who}] [{ampm} {t.hour % 12 or 12}:{t.minute:02d}] {rnd.choice(T[who])}")
    return "\n".join(lines)


def _gini(x):
    x = sorted(max(v, 0) for v in x)
    n = len(x)
    if n == 0 or sum(x) == 0:
        return 0.0
    cum = sum((i + 1) * v for i, v in enumerate(x))
    return (2 * cum) / (n * sum(x)) - (n + 1) / n


def analyze_team(df_all: pd.DataFrame, min_msgs=3, new_conv_hours=3, call_window_min=60) -> dict:
    counts = df_all["sender"].value_counts()
    members = counts[counts >= min_msgs].index.tolist()
    df = enrich(df_all[df_all["sender"].isin(members)], new_conv_hours)
    msg = df["message"]
    df["work"] = msg.str.contains(RE_WORK, regex=True).astype(int)
    df["lead"] = msg.str.contains(RE_LEAD, regex=True).astype(int)
    df["done"] = msg.str.contains(RE_DONE, regex=True).astype(int)
    df["file"] = msg.str.contains(RE_FILE, regex=True).astype(int)
    df["yes"] = msg.str.match(RE_YES).astype(int)
    df["night_work"] = (df["work"] == 1) & ((df["hour"] >= 23) | (df["hour"] < 5))

    # 호출 응답률: 다른 사람이 '주도' 메시지를 보낸 뒤 60분 안에 반응했는지
    calls = df[df["lead"] == 1][["time", "sender"]].values
    times = df["time"].values
    senders = df["sender"].values
    resp = {m: [0, 0] for m in members}
    import numpy as np
    for t, who in calls:
        lo = np.searchsorted(times, np.datetime64(t), side="right")
        hi = np.searchsorted(times, np.datetime64(t) + np.timedelta64(call_window_min, "m"), side="right")
        answered = set(senders[lo:hi])
        for m in members:
            if m == who:
                continue
            resp[m][1] += 1
            resp[m][0] += m in answered

    rows = {}
    for m in members:
        d = df[df["sender"] == m]
        n = max(len(d), 1)
        rows[m] = {
            "메시지": len(d),
            "업무 대화": int(d["work"].sum()),
            "완료 보고": int(d["done"].sum()),
            "자료 공유": int(d["file"].sum()),
            "주도(회의·분담)": int(d["lead"].sum()),
            "호출 응답률": resp[m][0] / resp[m][1] if resp[m][1] else 0.0,
            "'넵' 비율": float(d["yes"].sum() / n),
            "질문": int(d["question"].sum()),
            "ㅋ/메시지": float(d["kk"].sum() / n),
            "답장 속도(분)": _median_reply(d, 1),
            "야근 메시지": int(d["night_work"].sum()),
        }
    T = pd.DataFrame(rows).T

    # 기여도 (항목별 팀 내 최고 대비 비율 × 가중치)
    contrib = pd.Series(0.0, index=members)
    parts = {}
    for k, w in TEAM_WEIGHTS.items():
        col = T[k].astype(float)
        mx = col.max()
        part = (col / mx * w) if mx > 0 else col * 0
        parts[k] = part
        contrib += part
    T["기여도"] = contrib
    yes_ratio = T["'넵' 비율"].astype(float)
    T["무임승차 지수"] = (0.75 * (100 - contrib) + 25 * (yes_ratio / max(yes_ratio.max(), 0.01))).clip(0, 100)

    def fr_label(v):
        if v >= 70:
            return "🚨 무임승차 강력 의심"
        if v >= 50:
            return "👀 관찰 대상"
        if v >= 30:
            return "🙂 무난한 팀원"
        return "🦸 캐리 담당"
    T["판정"] = T["무임승차 지수"].map(fr_label)

    # 역할
    metric_for_role = {
        "lead": T["주도(회의·분담)"].astype(float), "file": T["자료 공유"].astype(float),
        "done": T["완료 보고"].astype(float), "kk": T["ㅋ/메시지"].astype(float),
        "ask": T["질문"].astype(float), "yes": T["'넵' 비율"].astype(float),
        "fast": -T["답장 속도(분)"].astype(float).fillna(999), "night": T["야근 메시지"].astype(float),
    }
    role_score = {}
    for r, col in metric_for_role.items():
        if r == "fast":
            v = 1 / (1 + T["답장 속도(분)"].astype(float).fillna(60))
            role_score[r] = v / v.sum() if v.sum() else v
        else:
            role_score[r] = col / col.sum() if col.sum() > 0 else col * 0
    RS = pd.DataFrame(role_score)
    roles, taken = {}, set()
    # 점유율이 가장 뚜렷한 조합부터 배정 (같은 역할은 한 명만)
    pairs = sorted(((RS.loc[m, r], m, r) for m in members for r in RS.columns), reverse=True)
    for score, m, r in pairs:
        if m in roles or r in taken or score <= 0:
            continue
        roles[m] = ROLES[r]
        taken.add(r)
    for m in members:
        roles.setdefault(m, ("🙂", "평범한 팀원", "튀지 않게 묻어가는 중"))
    T["역할"] = [f"{roles[m][0]} {roles[m][1]}" for m in members]

    # 팀 유형
    g = _gini(contrib.tolist())
    top_share = contrib.max() / contrib.sum() if contrib.sum() else 0
    work_rate = df["work"].mean()
    if work_rate < 0.08:
        ttype = ("😴", "다 같이 조용한 팀", "업무 얘기가 거의 없어요. 혹시 다른 방에서 일하나요?")
    elif top_share >= 0.4 or g >= 0.35:
        ttype = ("🦸", "원맨 캐리 팀", f"{contrib.idxmax()}님이 혼자 끌고 가는 중... 고생 많으세요")
    elif g < 0.15:
        ttype = ("⚖️", "N빵 정석 팀", "기여도가 고르게 나뉜 이상적인 팀이에요")
    else:
        ttype = ("🤝", "무난한 협업 팀", "몇 명이 조금 더 하지만 대체로 잘 굴러가요")

    # 마감 텐션
    daily = df.groupby("date").agg(메시지=("message", "size"), 업무=("work", "sum")).reset_index()
    daily["date"] = pd.to_datetime(daily["date"])
    crunch = daily.loc[daily["업무"].idxmax()] if len(daily) else None
    late = df[df["night_work"]]

    hl = []
    if crunch is not None:
        hl.append(("🔥", "마감 폭주의 날", f"{crunch['date']:%m월 %d일} — 업무 메시지 {int(crunch['업무'])}개"))
    first_call = df[df["lead"] == 1]
    if len(first_call):
        r = first_call.iloc[0]
        hl.append(("📣", "첫 회의 소집", f"{r['time']:%m월 %d일 %H:%M}, {r['sender']}님 — “{_clip(r['message'])}”"))
    if len(late):
        r = late.sort_values("hour", key=lambda h: (h + 19) % 24).iloc[-1]
        hl.append(("🌙", "가장 늦은 야근", f"{r['time']:%m월 %d일 %H:%M}, {r['sender']}님 — “{_clip(r['message'])}”"))
    ycount = df[df["yes"] == 1]["sender"].value_counts()
    if len(ycount):
        hl.append(("🙇", "'넵' 최다 보유자", f"{ycount.index[0]}님 — '넵·네·확인' 계열 {int(ycount.iloc[0])}회"))
    fcount = df[df["file"] == 1]["sender"].value_counts()
    if len(fcount):
        hl.append(("📁", "자료 폭탄", f"{fcount.index[0]}님이 파일·링크·사진 {int(fcount.iloc[0])}개 공유"))

    T = T.sort_values("기여도", ascending=False)
    return {"df": df, "members": members, "table": T, "parts": pd.DataFrame(parts), "type": ttype,
            "gini": g, "daily": daily, "highlights": hl, "mvp": T.index[0],
            "suspect": T["무임승차 지수"].idxmax()}


# ═════════════════════════════════════════════
# 8. 친구 모드
# ═════════════════════════════════════════════
RE_PLAN = r"밥 ?먹|술 ?마|한잔|만나|보자|볼래|언제 ?봄|놀자|놀러|ㄱㄱ|가자|갈래|약속|시간 ?돼|시간 ?되|콜\?|모이자|번개"
RE_CARE = r"괜찮아|괜찮냐|힘내|고생|수고|조심|아프지|푹 ?쉬|생일|축하|ㅊㅋ|응원|잘될|잘 될|화이팅|파이팅"
RE_DRIP = r"ㅅㅂ|시발|씨발|미친|ㅁㅊ|개웃|ㅈㄴ|존나|졸라|레전드|실화|ㄹㅇ|ㅋㅋㅋㅋㅋㅋ|킹받|어이없|돌았"
RE_SAD = r"ㅠ|ㅜ|힘들|우울|속상|짜증|스트레스|고민"

FRIEND_WEIGHTS = {"선톡": 30, "약속 제안": 25, "챙기는 말": 15, "답장 속도": 15, "리액션(ㅋ)": 15}


def make_friend_sample(me="승욱", you="도윤") -> str:
    rnd = random.Random(515)
    weekdays = "월화수목금토일"
    me_t = ["ㅋㅋㅋㅋㅋㅋㅋ 미친", "야 이거 봐 ㅋㅋㅋㅋ", "레전드다 진짜", "ㄹㅇ ㅋㅋㅋㅋ", "사진", "아 킹받네 ㅋㅋㅋ",
            "주말에 술 한잔 ㄱ?", "언제 봄?", "괜찮냐 요즘 힘들어 보이던데", "고생했다 ㅋㅋ", "이모티콘"]
    you_t = ["ㅋㅋㅋㅋㅋㅋㅋㅋ", "ㅇㅇ ㄱㄱ", "아 나 요즘 회사 때문에 좀 힘들다 ㅠㅠ 팀장이 맨날 야근시킴", "ㄹㅇ 개웃기네",
             "그래 토요일 콜", "ㅋㅋㅋ 미쳤냐", "고맙다 ㅋㅋ", "나 다음주 생일인거 알지?", "ㅇㅋ", "이모티콘", "사진"]
    start = datetime(2026, 9, 1)
    lines = [f"{you} 님과 카카오톡 대화", ""]
    for day in range(0, 72):
        d = start + timedelta(days=day)
        p = 0.55 if day < 50 else 0.25  # 최근엔 연락이 좀 뜸해짐
        if rnd.random() > p:
            continue
        lines.append(f"--------------- {d.year}년 {d.month}월 {d.day}일 {weekdays[d.weekday()]}요일 ---------------")
        t = d.replace(hour=rnd.randint(12, 23), minute=rnd.randint(0, 50))
        who = me if rnd.random() < 0.6 else you
        for _ in range(rnd.randint(4, 16)):
            pool = me_t if who == me else you_t
            ampm = "오전" if t.hour < 12 else "오후"
            lines.append(f"[{who}] [{ampm} {t.hour % 12 or 12}:{t.minute:02d}] {rnd.choice(pool)}")
            t += timedelta(minutes=rnd.choice([0, 1, 1, 2, 4, 10]))
            if t.date() != d.date():
                break
            who = you if who == me else me
    return "\n".join(lines)


def _friend_flags(df):
    msg = df["message"]
    df["plan"] = msg.str.contains(RE_PLAN, regex=True).astype(int)
    df["care"] = msg.str.contains(RE_CARE, regex=True).astype(int)
    df["drip"] = msg.str.count(RE_DRIP)
    df["deep"] = ((df["len"] >= 35) | msg.str.contains(RE_SAD, regex=True) & (df["len"] >= 15)).astype(int)
    return df


def friend_person(df, p):
    d = df[df["sender"] == p]
    n = max(len(d), 1)
    base = person_stats(df, p)
    base.update({
        "약속 제안": int(d["plan"].sum()),
        "챙기는 말": int(d["care"].sum()),
        "드립·찐반응": int(d["drip"].sum()),
        "진지한 대화": int(d["deep"].sum()),
        "_plan_rate": d["plan"].sum() / n, "_care_rate": d["care"].sum() / n,
        "_drip_rate": d["drip"].sum() / n, "_deep_rate": d["deep"].sum() / n,
    })
    return base


def friend_type(s, o):
    tot = s["선톡 횟수"] + o["선톡 횟수"]
    share = s["선톡 횟수"] / tot if tot else 0.5
    tail = "먼저 연락하는 쪽" if share >= 0.56 else ("연락 받는 쪽" if share <= 0.44 else "쌍방 연락파")
    r = s["답장 속도(분, 중앙값)"]
    traits = [
        (s["_drip_rate"] >= 0.35, "드립 장인", "대화의 8할이 드립"),
        (s["_deep_rate"] >= 0.12, "고민 상담소장", "진지한 얘기는 이 사람이 다 함"),
        (s["_care_rate"] >= 0.08, "공감 요정", "힘들 땐 먼저 챙겨주는"),
        (s["_plan_rate"] >= 0.08, "약속 총무", "'언제 봄?'은 늘 이 사람 몫"),
        (s["ㅋ/메시지"] >= 1.5, "리액션 머신", "ㅋ를 숨 쉬듯이 생산"),
        (not math.isnan(r) and r < 1.5, "칼답러", "알림 뜨자마자 답장"),
        (s["새벽 메시지"] >= 10, "새벽 수다러", "새벽에 더 말이 많아짐"),
        (0 < s["평균 글자 수"] < 6, "단답 장인", "ㅇㅇ ㅇㅋ로 대화 가능"),
    ]
    for ok, name, d in traits:
        if ok:
            return name, f"{d} · {tail}"
    return "무난한 친구", f"모든 게 평균 · {tail}"


def friend_verdict(temp, score_a, trend, a, b):
    diff = score_a - 50
    lead, follow = (a, b) if diff > 0 else (b, a)
    if temp >= 60 and abs(diff) < 8:
        return "💎", "평생 베프", "서로 챙기고 서로 웃기는, 이미 가족 같은 사이"
    if temp >= 60:
        return "🐶", "한쪽이 더 챙기는 베프", f"{lead}님이 더 챙기는 중. {follow}님, 이번엔 먼저 연락해 보세요!"
    if temp < 40 and trend < -0.2:
        return "🌫️", "연락 끊기기 직전", "요즘 대화가 확 줄었어요. 지금 '밥 한번 먹자' 보내면 살릴 수 있어요"
    if temp >= 40:
        return "🍻", "놀 때 부르는 친구", "자주는 아니어도 만나면 재밌는 사이"
    return "📞", "용건만 친구", "필요할 때만 연락하는 쿨한 사이"


def analyze_friend_pair(df_all, a, b, new_conv_hours=6):
    df = _friend_flags(enrich(df_all[df_all["sender"].isin([a, b])], new_conv_hours))
    sa, sb = friend_person(df, a), friend_person(df, b)
    ra = 30 if math.isnan(sa["답장 속도(분, 중앙값)"]) else sa["답장 속도(분, 중앙값)"]
    rb = 30 if math.isnan(sb["답장 속도(분, 중앙값)"]) else sb["답장 속도(분, 중앙값)"]
    parts = {
        "선톡": _share(sa["선톡 횟수"], sb["선톡 횟수"]),
        "약속 제안": _share(sa["약속 제안"], sb["약속 제안"]),
        "챙기는 말": _share(sa["챙기는 말"], sb["챙기는 말"]),
        "답장 속도": _share(rb + 0.5, ra + 0.5),
        "리액션(ㅋ)": _share(sa["ㅋ/메시지"], sb["ㅋ/메시지"]),
    }
    score_a = sum(FRIEND_WEIGHTS[k] * v for k, v in parts.items())

    # 우정 온도
    span_weeks = max(((df["time"].max() - df["time"].min()).days + 1) / 7, 1)
    weeks_active = df["time"].dt.to_period("W").nunique()
    consistency = min(1, weeks_active / span_weeks)
    days_active = df["date"].nunique()
    mpd = len(df) / max(days_active, 1)
    last = df["time"].max()
    recent = int((df["time"] > last - timedelta(days=14)).sum())
    prev = int(((df["time"] <= last - timedelta(days=14)) & (df["time"] > last - timedelta(days=28))).sum())
    trend = (recent - prev) / max(recent, prev, 1)
    kk_rate = df["kk"].sum() / max(len(df), 1)
    deep_rate = df["deep"].mean()
    temp = (30 * consistency + 20 * min(1, mpd / 40) + 20 * min(1, kk_rate / 1.2)
            + 15 * min(1, deep_rate / 0.06) + 15 * (0.5 + trend / 2))
    emoji, title, desc = friend_verdict(temp, score_a, trend, a, b)

    # 연락 공백
    dates = sorted(set(df["date"]))
    gaps = [((dates[i] - dates[i - 1]).days, dates[i - 1], dates[i]) for i in range(1, len(dates))]
    longest = max(gaps) if gaps else (0, None, None)

    hl = []
    first, lastt = df["time"].min(), df["time"].max()
    hl.append(("📆", "우리의 기록", f"{first:%Y.%m.%d} ~ {lastt:%Y.%m.%d} · {days_active}일 대화, 총 {len(df):,}개 메시지"))
    kkday = df.groupby("date")["kk"].sum()
    hl.append(("😂", "가장 많이 웃은 날", f"{kkday.idxmax():%m월 %d일} — ㅋ {int(kkday.max())}개"))
    if longest[0] >= 2:
        hl.append(("🕳️", "최장 연락 공백", f"{longest[1]:%m월 %d일} ~ {longest[2]:%m월 %d일}, {longest[0]}일 동안 조용"))
    plan = df[df["plan"] == 1]
    if len(plan):
        r = plan.iloc[0]
        hl.append(("🍚", "첫 약속 제안", f"{r['time']:%m월 %d일}, {r['sender']}님 — “{_clip(r['message'])}”"))
    deep = df[df["deep"] == 1]
    if len(deep):
        r = deep.loc[deep["len"].idxmax()]
        hl.append(("🫂", "가장 진지했던 순간", f"{r['time']:%m월 %d일}, {r['sender']}님 — “{_clip(r['message'], 34)}”"))
    care = df[df["care"] == 1]["sender"].value_counts()
    if len(care):
        hl.append(("💛", "챙김 담당", f"{care.index[0]}님 — '괜찮아?·고생했어' 계열 {int(care.iloc[0])}회"))

    warn = None
    if trend < -0.3:
        warn = f"최근 2주 대화가 그 전 2주보다 {abs(trend):.0%} 줄었어요. 먼저 '요즘 뭐하고 지내?' 한마디 어때요?"

    return {"df": df, "stats": {a: sa, b: sb}, "score_a": score_a, "parts": parts, "temp": temp,
            "emoji": emoji, "title": title, "desc": desc, "trend": trend, "recent": recent, "prev": prev,
            "mpd": mpd, "consistency": consistency,
            "types": {a: friend_type(sa, sb), b: friend_type(sb, sa)},
            "highlights": hl, "warn": warn, "words": {a: top_words(df, a), b: top_words(df, b)}}


FRIEND_ROLES = [
    ("kk", "🎉", "분위기 메이커", "메시지당 ㅋ 최다"),
    ("drip", "🤪", "드립 담당", "드립·찐반응 최다"),
    ("plan", "🍚", "약속 총무", "'언제 봄?' 최다 발언"),
    ("care", "💛", "엄마 담당", "챙기는 말 최다"),
    ("deep", "🫂", "고민 상담소", "진지한 얘기 최다"),
    ("photo", "📸", "사진 작가", "사진·이모티콘 최다"),
    ("dawn", "🌙", "새벽 지킴이", "새벽 메시지 최다"),
    ("lurk", "👀", "눈팅러", "있는 듯 없는 듯"),
]


def analyze_friend_group(df_all, min_msgs=3):
    G = analyze_group(df_all, min_msgs=min_msgs)
    df = _friend_flags(G["df"])
    df["pic"] = df["photo"] + df["emoticon"]
    members = G["members"]
    agg = df.groupby("sender").agg(n=("message", "size"), kk=("kk", "sum"), drip=("drip", "sum"),
                                   plan=("plan", "sum"), care=("care", "sum"), deep=("deep", "sum"),
                                   photo=("pic", "sum"), dawn=("dawn", "sum")).reindex(members).fillna(0)
    rates = agg.drop(columns="n").div(agg["n"].clip(lower=1), axis=0)
    rates["dawn"] = agg["dawn"]  # 새벽은 절대 개수
    rates["lurk"] = 1 / agg["n"].clip(lower=1)
    roles, taken = {}, set()
    cand = []
    for key, *_ in FRIEND_ROLES:
        col = rates[key]
        if col.sum() > 0:
            for m in members:
                cand.append((col[m] / col.sum(), m, key))
    for sc, m, key in sorted(cand, reverse=True):
        if m in roles or key in taken or sc <= 0:
            continue
        roles[m] = key
        taken.add(key)
    role_info = {k: (e, n, d) for k, e, n, d in FRIEND_ROLES}
    role_list = [(role_info[roles[m]][0], role_info[roles[m]][1], m, role_info[roles[m]][2])
                 for m in members if m in roles]

    # 단톡 생존율
    last = df["time"].max()
    recent = int((df["time"] > last - timedelta(days=14)).sum())
    prev = int(((df["time"] <= last - timedelta(days=14)) & (df["time"] > last - timedelta(days=28))).sum())
    trend = (recent - prev) / max(recent, prev, 1)
    active_share = (df[df["time"] > last - timedelta(days=14)]["sender"].nunique()) / max(len(members), 1)
    survival = max(3, min(99, 50 + 30 * trend + 20 * (active_share - 0.5) * 2))
    if survival >= 80:
        sv = "🔥 아주 팔팔하게 살아있는 방"
    elif survival >= 55:
        sv = "🙂 잘 굴러가는 중"
    elif survival >= 30:
        sv = "😮‍💨 슬슬 조용해지는 중"
    else:
        sv = "🪦 곧 화석이 될 위기"
    return {**G, "df": df, "roles": role_list, "survival": survival, "survival_label": sv,
            "trend": trend, "recent": recent, "prev": prev, "active_share": active_share}
