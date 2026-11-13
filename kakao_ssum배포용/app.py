"""
💘 카톡 관계 분석기 (썸 · 친구 · 팀플)
실행:  streamlit run app.py
"""

import random

import altair as alt
import pandas as pd
import streamlit as st

import analyzer as A
from share_card import make_card, make_group_card

st.set_page_config(page_title="카톡 관계 분석기", page_icon="💘", layout="wide")

PINK, BLUE = "#ff5c8a", "#5c8aff"
MAX_MB = 50

st.markdown(
    """
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css');
    .stApp, .stMarkdown, .stMarkdown p, h1, h2, h3, h4, label, [data-testid="stMetricValue"],
    [data-testid="stMetricLabel"], .stTabs button p {font-family: 'Pretendard', -apple-system, sans-serif !important;}
    h2, h3 {font-weight: 800 !important; letter-spacing: -0.02em;}
    [data-testid="stMetric"] {background:#fff; border:1px solid #f0e6ea; border-radius:18px; padding:.8rem 1rem;
                              box-shadow: 0 4px 14px rgba(255,92,138,.06);}
    .stTabs [data-baseweb="tab"] {font-weight:700;}
    .hero {border-radius: 26px; padding: 1.8rem 1.5rem 1.5rem; text-align:center; color:white; margin-bottom:1rem;
           box-shadow: 0 10px 30px rgba(0,0,0,.08);}
    .hero h1 {color:white !important; font-size:2.6rem; font-weight:900; margin:0; padding:0;}
    .hero p {color:rgba(255,255,255,.92); margin:.3rem 0 0; font-size:1.05rem;}
    .card, .award, .hl {transition: transform .15s ease;}
    .award:hover, .hl:hover {transform: translateY(-2px);}
    .big-title {font-size: 2.8rem; font-weight: 800; text-align:center; margin-bottom:0;
                background: linear-gradient(90deg,#ff5c8a,#ffb199);
                -webkit-background-clip: text; -webkit-text-fill-color: transparent;}
    .sub {text-align:center; color:#999; margin-bottom: 1.2rem;}
    .card {background: linear-gradient(135deg,#fff0f5,#fff7f0); border-radius: 22px;
           padding: 1.4rem 1.6rem; border: 1px solid #ffd1e0;}
    .verdict-emoji {font-size: 3.2rem; text-align:center; line-height:1.1;}
    .verdict {font-size: 2.1rem; font-weight: 800; text-align:center; color:#ff5c8a;}
    .verdict-sub {text-align:center; font-size: 1.1rem; color:#555;}
    .chip {display:inline-block; padding:.35rem .8rem; margin:.2rem; border-radius:999px;
           font-size:.92rem; font-weight:600; border:1px solid;}
    .hl {background:#fff; border:1px solid #f1e3e8; border-radius:16px; padding:.9rem 1.1rem; margin-bottom:.6rem;}
    .hl b {color:#ff5c8a;}
    .award {text-align:center; background:#fff7fa; border-radius:18px; padding:1rem .5rem; border:1px solid #ffd1e0;}
    .award .e {font-size:2.2rem;} .award .n {font-weight:800; font-size:1.15rem;} .award .d {color:#888; font-size:.85rem;}
    .heart {position: fixed; top: -2rem; font-size: 1.7rem; z-index: 9999;
            animation: fall linear forwards; pointer-events: none;}
    @keyframes fall { to { transform: translateY(110vh) rotate(360deg); opacity: .15; } }
    </style>
    """,
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────
# 캐시된 로딩/분석
# ─────────────────────────────────────────────
CACHE_VER = "v4"  # 분석 로직이 바뀌면 숫자를 올려서 예전 캐시를 무시


@st.cache_data(show_spinner=False)
def load(raw: bytes, name: str, ver=CACHE_VER):
    return A.parse_kakao(raw, name)


@st.cache_data(show_spinner=False)
def run_pair(df, a, b, hours, ver=CACHE_VER):
    return A.analyze_pair(df, a, b, hours)


@st.cache_data(show_spinner=False)
def run_group(df, ver=CACHE_VER):
    return A.analyze_group(df)


@st.cache_data(show_spinner=False)
def card_png(a, b, title, desc, temp, score_a, stats, couple, ta, tb, prob, when, ver=CACHE_VER):
    return make_card(a, b, title, desc, temp, score_a, stats, couple, ta, tb, prob, when)


@st.cache_data(show_spinner=False)
def group_card_png(room, n, msgs, period, awards, pairs, ver=CACHE_VER):
    return make_group_card(room, n, msgs, period, awards, pairs)


def chips(items, color):
    return "".join(f'<span class="chip" style="color:{color};border-color:{color}55;background:{color}12" '
                   f'title="{d}">{e} {n}</span>' for e, n, d in items)


def rain_hearts(n=28):
    st.markdown("".join(
        f'<div class="heart" style="left:{random.randint(0, 97)}vw;'
        f'animation-duration:{random.uniform(2.5, 5.5):.1f}s;animation-delay:{random.uniform(0, 2):.1f}s">'
        f'{random.choice(["💖", "💗", "💘", "💕", "❤️"])}</div>' for _ in range(n)), unsafe_allow_html=True)


# ─────────────────────────────────────────────
# 사이드바
# ─────────────────────────────────────────────
MODES = {
    "💘 썸": ("💘 카톡 썸 분석기", "그 사람 마음, 숫자로 확인해 보세요", "linear-gradient(120deg,#ff5c8a,#ffb199)",
              {"💑 1:1 썸 샘플": A.make_sample, "👥 단톡방 샘플": A.make_group_sample}),
    "👯 친구": ("👯 카톡 우정 분석기", "우리 우정, 몇 도일까?", "linear-gradient(120deg,#16b894,#ffd15c)",
              {"👯 1:1 친구 샘플": A.make_friend_sample, "👥 단톡방 샘플": A.make_group_sample}),
    "🛠️ 팀플": ("🛠️ 카톡 팀플 분석기", "누가 캐리하고, 누가 묻어갔을까?", "linear-gradient(120deg,#3a60ff,#78dcff)",
              {"🛠️ 팀플 단톡 샘플": A.make_team_sample}),
}

with st.sidebar:
    st.header("🔮 분석 모드")
    MODE = st.radio("분석 모드", list(MODES), index=0, horizontal=True, label_visibility="collapsed")
    st.divider()
    st.header("📂 대화 불러오기")
    up = st.file_uploader("카카오톡 대화 내보내기 파일 (.txt / .csv)", type=["txt", "csv"])
    sample = st.radio("또는 샘플로 체험", list(MODES[MODE][3]), index=0,
                      disabled=up is not None, horizontal=False)
    with st.expander("📱 내보내기 방법"):
        st.markdown(
            "- **PC**: 채팅방 ≡ 메뉴 → 대화 내용 → 대화 내보내기\n"
            "- **모바일**: 채팅방 ≡ → ⚙️ 설정 → 대화 내용 내보내기 → *텍스트만 보내기*\n"
            "- 한국어/영어 설정, PC·안드로이드·아이폰·CSV 모두 지원")
    st.divider()
    st.subheader("🛡️ 개인정보 보호")
    pseudo = st.toggle("이름 가명 처리 (발표·캡처용)", value=False,
                       help="실제 이름을 '하트', '별' 같은 가명으로 바꿔서 보여줘요.")
    st.caption("전화번호·이메일·링크·긴 숫자(계좌 등)는 항상 자동으로 가려져요.")
    with st.expander("⚙️ 고급 설정"):
        hours = st.slider("새 대화로 보는 공백 (시간)", 1, 24, 6,
                          help="이 시간 이상 대화가 끊긴 뒤 보낸 첫 메시지를 '선톡'으로 셉니다.")
    st.divider()
    st.caption("🔒 업로드한 대화는 분석하는 동안 서버 메모리에만 잠시 올라가고, 파일로 저장되거나 "
               "다른 곳으로 보내지지 않아요. 창을 닫으면 사라져요. "
               "단, 대화에는 상대방의 말도 들어 있으니 다른 사람에게 공유할 땐 꼭 동의를 받아주세요.")

# ─────────────────────────────────────────────
# 데이터 로딩
# ─────────────────────────────────────────────
_t, _s, _g, _ = MODES[MODE]
st.markdown(f'<div class="hero" style="background:{_g}"><h1>{_t}</h1><p>{_s}</p></div>', unsafe_allow_html=True)

is_sample = up is None
try:
    if up is not None:
        if up.size > MAX_MB * 1024 * 1024:
            st.error(f"파일이 너무 커요 ({up.size / 1024 / 1024:.0f}MB). {MAX_MB}MB 이하로 기간을 줄여서 내보내 주세요.")
            st.stop()
        with st.spinner("대화를 읽는 중... 💌"):
            raw_df = load(up.getvalue(), up.name)
            ROOM = A.room_name(up.getvalue())
    else:
        text = MODES[MODE][3][sample]()
        raw_df = load(text.encode("utf-8"), "sample.txt")
        ROOM = A.room_name(text.encode("utf-8"))
except Exception as e:  # noqa: BLE001
    st.error("파일을 읽다가 문제가 생겼어요 😢 카카오톡에서 내보낸 원본 파일이 맞는지 확인해 주세요.")
    with st.expander("오류 자세히"):
        st.code(str(e))
    st.stop()

if raw_df.empty:
    st.error("대화를 하나도 찾지 못했어요 😢 카카오톡 '대화 내보내기' 원본(.txt/.csv) 파일인지 확인해 주세요.")
    st.stop()

df_all, _ = A.anonymize(raw_df, pseudo)

# 기간 필터
dmin, dmax = df_all["time"].min().date(), df_all["time"].max().date()
with st.sidebar:
    if dmin < dmax:
        period = st.date_input("📅 분석 기간", (dmin, dmax), min_value=dmin, max_value=dmax)
        if isinstance(period, (tuple, list)) and len(period) == 2:
            df_all = df_all[(df_all["time"].dt.date >= period[0]) & (df_all["time"].dt.date <= period[1])]

senders = df_all["sender"].value_counts()
if len(senders) < 2:
    st.error("대화 참여자가 2명 이상이어야 분석할 수 있어요.")
    st.stop()

if is_sample:
    st.info("👀 지금은 **샘플 대화**를 보여주는 중이에요. 왼쪽에서 내 카톡 파일을 올려보세요!")

if MODE != "💘 썸":
    import ui_modes
    if MODE == "👯 친구":
        ui_modes.render_friend(df_all, ROOM, pseudo, hours)
    else:
        ui_modes.render_team(df_all, ROOM, pseudo)
    st.stop()

is_group = len(senders) > 2
tab_names = ["💘 1:1 썸 분석"] + (["👥 단톡방 분석"] if is_group else []) + ["ℹ️ 분석 방법"]
tabs = st.tabs(tab_names)
tab_pair, tab_info = tabs[0], tabs[-1]
tab_group = tabs[1] if is_group else None

# ═════════════════════════════════════════════
# 1:1 분석 탭
# ═════════════════════════════════════════════
with tab_pair:
    names = senders.index.tolist()
    if is_group:
        st.caption("단톡방이에요. 분석할 두 사람을 골라주세요. (👥 탭에서 '썸 의심 커플'을 먼저 확인해 보세요!)")
    c1, c2 = st.columns(2)
    a = c1.selectbox("🙋 나", names, index=0)
    b = c2.selectbox("💗 그 사람", [s for s in names if s != a], index=0)

    with st.spinner("마음을 분석하는 중... 💘"):
        R = run_pair(df_all, a, b, hours)
    S = R["stats"]

    if len(R["df"]) < 50:
        st.warning(f"두 사람의 메시지가 {len(R['df'])}개뿐이라 결과가 들쭉날쭉할 수 있어요. 대화가 많을수록 정확해져요!")

    st.markdown(
        f'<div class="card"><div class="verdict-emoji">{R["emoji"]}</div>'
        f'<div class="verdict">{R["title"]}</div><div class="verdict-sub">{R["desc"]}</div></div>',
        unsafe_allow_html=True)
    if R["emoji"] in ("💞", "🔥"):
        rain_hearts()

    st.write("")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🌡️ 썸 온도", f"{R['temp']:.0f}°")
    m2.metric(f"💗 {b}님 마음 지분", f"{100 - R['score_a']:.0f}%", f"{(100 - R['score_a']) - 50:+.0f}%p vs 반반")
    m3.metric("💬 하루 평균 메시지", f"{R['mpd']:.0f}개", help="대화한 날 기준")
    trend_txt = "📈 상승세" if R["trend"] > 0.1 else ("📉 하락세" if R["trend"] < -0.1 else "➡️ 유지")
    m4.metric("최근 7일 흐름", trend_txt, f"{R['recent'] - R['prev']:+d}개 (직전 7일 대비)")

    # ── 썸 유형 + 고백 성공 확률
    st.write("")
    cn, cd = R["couple"]
    CF = R["confess"]
    st.markdown(
        f"""
        <div style="display:flex;gap:16px;flex-wrap:wrap">
          <div class="card" style="flex:1.3;min-width:300px">
            <div style="color:#ff5c8a;font-weight:700">🧬 우리의 썸 유형</div>
            <div style="font-size:1.8rem;font-weight:800;margin:.2rem 0">{cn}</div>
            <div style="color:#888;margin-bottom:.8rem">{cd}</div>
            <div style="display:flex;gap:10px;flex-wrap:wrap">
              <div style="flex:1;min-width:180px;background:#eef2ff;border-radius:16px;padding:.8rem 1rem">
                <div style="color:{BLUE};font-weight:700">{a}</div>
                <div style="font-size:1.25rem;font-weight:800">{R['types'][a][0]}</div>
                <div style="color:#666;font-size:.9rem">{R['types'][a][1]}</div></div>
              <div style="flex:1;min-width:180px;background:#ffeef4;border-radius:16px;padding:.8rem 1rem">
                <div style="color:{PINK};font-weight:700">{b}</div>
                <div style="font-size:1.25rem;font-weight:800">{R['types'][b][0]}</div>
                <div style="color:#666;font-size:.9rem">{R['types'][b][1]}</div></div>
            </div>
          </div>
          <div class="card" style="flex:1;min-width:280px;text-align:center;background:linear-gradient(135deg,#fff4ea,#fff0f5)">
            <div style="color:#f08a24;font-weight:700">💍 {b}님에게 고백하면?</div>
            <div style="font-size:3.6rem;font-weight:900;color:#f08a24;line-height:1.1;margin:.3rem 0">{CF['prob']:.0f}%</div>
            <div style="font-weight:700;margin-bottom:.6rem">{CF['label']}</div>
            <div style="background:#fff;border-radius:999px;padding:.45rem .9rem;display:inline-block;font-weight:700">
              📅 추천 타이밍: {CF['when']} · {CF['dday']}</div>
            <div style="color:#999;font-size:.85rem;margin-top:.4rem">{CF['why']}</div>
          </div>
        </div>
        """.replace("\n", " ").strip(), unsafe_allow_html=True)

    # ── 칭호
    st.subheader("🏅 획득한 칭호")
    b1, b2 = st.columns(2)
    b1.markdown(f"**{a}**<br>{chips(R['badges'][a], BLUE)}", unsafe_allow_html=True)
    b2.markdown(f"**{b}**<br>{chips(R['badges'][b], PINK)}", unsafe_allow_html=True)
    st.caption("칭호에 마우스를 올리면 근거가 보여요.")

    # ── 마음의 지분
    st.subheader("⚖️ 누가 더 좋아할까? — 마음의 지분")
    pa = R["score_a"]
    st.markdown(
        f"""<div style="display:flex;height:46px;border-radius:23px;overflow:hidden;font-weight:700;color:white">
          <div style="width:{pa:.1f}%;background:{BLUE};display:flex;align-items:center;justify-content:center">{a} {pa:.0f}%</div>
          <div style="width:{100 - pa:.1f}%;background:{PINK};display:flex;align-items:center;justify-content:center">{b} {100 - pa:.0f}%</div>
        </div>""", unsafe_allow_html=True)
    bd = pd.DataFrame([{"항목": f"{k} ({A.WEIGHTS[k]}점)", "사람": p, "비율": v if p == a else 1 - v}
                       for k, v in R["parts"].items() for p in (a, b)])
    st.altair_chart(
        alt.Chart(bd).mark_bar().encode(
            y=alt.Y("항목:N", sort=None, title=None),
            x=alt.X("비율:Q", stack="normalize", axis=alt.Axis(format="%"), title=None),
            color=alt.Color("사람:N", title="", scale=alt.Scale(domain=[a, b], range=[BLUE, PINK])),
            tooltip=["항목", "사람", alt.Tooltip("비율:Q", format=".0%")],
        ).properties(height=270), use_container_width=True)

    # ── 타임라인
    st.subheader("📆 썸 타임라인 — 주차별 마음의 변화")
    tl = R["timeline"]
    if len(tl) >= 2:
        tl_long = tl.melt(id_vars=["주", "메시지", "답장(분)"], value_vars=[a, b], var_name="사람", value_name="지분")
        line = alt.Chart(tl_long).mark_line(point=alt.OverlayMarkDef(size=80), strokeWidth=3).encode(
            x=alt.X("주:T", title=None, axis=alt.Axis(format="%m/%d")),
            y=alt.Y("지분:Q", scale=alt.Scale(domain=[0, 100]), title="마음의 지분 (%)"),
            color=alt.Color("사람:N", title="", scale=alt.Scale(domain=[a, b], range=[BLUE, PINK])),
            tooltip=[alt.Tooltip("주:T", format="%m/%d 주"), "사람", alt.Tooltip("지분:Q", format=".0f"), "메시지"])
        rule = alt.Chart(pd.DataFrame({"y": [50]})).mark_rule(strokeDash=[6, 4], color="#bbb").encode(y="y:Q")
        bars = alt.Chart(tl).mark_bar(opacity=.25, color="#ff9fbf").encode(
            x="주:T", y=alt.Y("메시지:Q", title="주간 메시지"))
        st.altair_chart(alt.layer(bars, rule + line).resolve_scale(y="independent").properties(height=320),
                        use_container_width=True)
        hot = tl.loc[tl["메시지"].idxmax()]
        gap_first, gap_last = abs(tl.iloc[0][a] - 50), abs(tl.iloc[-1][a] - 50)
        msg = "점점 **균형**을 찾아가는 중 → 쌍방으로 가는 흐름!" if gap_last < gap_first - 3 else \
            ("점점 **한쪽으로 기우는** 중..." if gap_last > gap_first + 3 else "처음과 비슷한 균형을 유지 중")
        st.caption(f"🔥 가장 뜨거웠던 주: **{hot['주']:%m월 %d일} 주** (메시지 {int(hot['메시지'])}개) · {msg}")
    else:
        st.caption("2주 이상 대화가 있어야 타임라인을 그릴 수 있어요.")

    # ── 명장면
    st.subheader("🎬 우리의 명장면")
    hl = R["highlights"]
    h1, h2 = st.columns(2)
    for i, (e, t, d) in enumerate(hl):
        (h1 if i % 2 == 0 else h2).markdown(f'<div class="hl">{e} <b>{t}</b><br>{d}</div>', unsafe_allow_html=True)

    # ── 상세 비교
    st.subheader("📊 1:1 상세 비교")
    rows = []
    for k in S[a]:
        if k.startswith("_"):
            continue
        row = {"항목": k}
        for p in (a, b):
            v = S[p][k]
            if k in ("질문 비율", "연타 비율"):
                row[p] = f"{v:.0%}"
            elif k.startswith("답장 속도"):
                row[p] = "-" if pd.isna(v) else f"{v:.1f}분"
            elif k in ("평균 글자 수", "ㅋ/메시지"):
                row[p] = f"{v:.1f}"
            else:
                row[p] = f"{int(v):,}"
        rows.append(row)
    st.dataframe(pd.DataFrame(rows).set_index("항목"), use_container_width=True)

    df = R["df"]
    color = alt.Color("sender:N", title="", scale=alt.Scale(domain=[a, b], range=[BLUE, PINK]))
    t1, t2, t3, t4 = st.tabs(["📅 날짜별 대화량", "🕐 시간대", "⏱️ 답장 속도", "🔤 말버릇"])
    with t1:
        daily = df.groupby(["date", "sender"]).size().reset_index(name="메시지")
        daily["date"] = pd.to_datetime(daily["date"])
        st.altair_chart(alt.Chart(daily).mark_line(point=True, strokeWidth=3).encode(
            x=alt.X("date:T", title=None), y="메시지:Q", color=color,
            tooltip=["date:T", "sender", "메시지"]).properties(height=320), use_container_width=True)
    with t2:
        hourly = df.groupby(["hour", "sender"]).size().reset_index(name="메시지")
        st.altair_chart(alt.Chart(hourly).mark_bar().encode(
            x=alt.X("hour:O", title="시"), y="메시지:Q", color=color, xOffset="sender:N",
            tooltip=["hour", "sender", "메시지"]).properties(height=320), use_container_width=True)
        dawn = int(df["dawn"].sum())
        st.caption(f"🌙 새벽(0~4시) 메시지 {dawn}개 — " + ("새벽 감성 공유 중..." if dawn > 5 else "건전한 낮 연락파"))
    with t3:
        rep = df[df["is_reply"] & (df["gap_min"] <= 6 * 60)].copy()
        labels = ["1분 이내", "1~5분", "5~30분", "30분~1시간", "1~3시간", "3시간+"]
        rep["구간"] = pd.cut(rep["gap_min"], bins=[-0.1, 1, 5, 30, 60, 180, 1e9], labels=labels)
        dist = rep.groupby(["구간", "sender"], observed=False).size().reset_index(name="횟수")
        st.altair_chart(alt.Chart(dist).mark_bar().encode(
            x=alt.X("구간:N", sort=labels, title=None), y="횟수:Q", color=color, xOffset="sender:N",
            tooltip=["구간", "sender", "횟수"]).properties(height=320), use_container_width=True)
        for p in (a, b):
            r = S[p]["답장 속도(분, 중앙값)"]
            if not pd.isna(r):
                tag = "⚡ 칼답" if r < 2 else ("🙂 적당" if r < 15 else "🐢 느긋")
                st.write(f"**{p}** : 보통 {r:.1f}분 안에 답장 → {tag}")
    with t4:
        w1, w2 = st.columns(2)
        for col, p, c in ((w1, a, BLUE), (w2, b, PINK)):
            w = pd.DataFrame(R["words"][p], columns=["단어", "횟수"])
            col.markdown(f"**{p}**의 말버릇")
            if w.empty:
                col.write("데이터 부족")
                continue
            col.altair_chart(alt.Chart(w).mark_bar(color=c, cornerRadiusEnd=4).encode(
                y=alt.Y("단어:N", sort="-x", title=None), x="횟수:Q").properties(height=330),
                use_container_width=True)

    # ── 한마디
    st.subheader("💌 분석가 한마디")
    for t in R["tips"]:
        st.write(t)

    # ── 공유 카드
    st.subheader("📸 결과 카드 공유하기")
    png = card_png(a, b, R["title"], R["desc"], R["temp"], R["score_a"], S, R["couple"],
                   R["types"][a], R["types"][b], R["confess"]["prob"], R["confess"]["when"])
    if png:
        pc1, pc2 = st.columns([1, 1.4])
        pc1.image(png, use_container_width=True)
        with pc2:
            st.markdown("인스타 스토리 사이즈(1080×1920)로 만들어졌어요.\n\n"
                        "- 상대 이름이 걱정되면 왼쪽에서 **가명 처리**를 켜고 받으세요.\n"
                        "- 대화 원문은 카드에 들어가지 않아요.")
            st.download_button("⬇️ 결과 카드 다운로드 (PNG)", png, file_name="ssum_report.png",
                               mime="image/png", type="primary", use_container_width=True)
    else:
        st.warning("한글 폰트를 찾지 못해 카드를 만들 수 없어요. `fonts/` 폴더에 한글 .ttf 파일(예: 나눔고딕)을 넣어주세요.")

    st.caption("※ 재미로 보는 분석입니다. 진짜 마음은 직접 물어보세요 😉")

# ═════════════════════════════════════════════
# 단톡방 탭
# ═════════════════════════════════════════════
if tab_group is not None:
    with tab_group:
        G = run_group(df_all)
        if len(G["members"]) < 3:
            st.info("메시지를 5개 이상 보낸 사람이 3명 미만이라 단톡방 분석이 어려워요.")
        else:
            st.subheader("🏆 단톡방 어워즈")
            cols = st.columns(len(G["awards"]))
            for col, (e, n, who, d) in zip(cols, G["awards"]):
                col.markdown(f'<div class="award"><div class="e">{e}</div><div class="n">{n}</div>'
                             f'<div style="font-size:1.2rem;font-weight:700;color:{PINK}">{A.short_name(who)}</div>'
                             f'<div class="d">{d}</div></div>', unsafe_allow_html=True)

            st.subheader("💘 썸 의심 커플 TOP 3")
            st.caption("서로의 말에 10분 안에 답한 횟수를 두 사람 전체 메시지 수로 나눈 '케미 지수' 기준이에요.")
            top = G["pairs"].head(3)
            pc = st.columns(3)
            for i, (col, (_, r)) in enumerate(zip(pc, top.iterrows())):
                medal = ["🥇", "🥈", "🥉"][i]
                spd = "-" if pd.isna(r["평균 답장(분)"]) else f"{r['평균 답장(분)']:.1f}분"
                col.markdown(f'<div class="award"><div class="e">{medal}</div><div class="n">{A.short_name(r["a"])} ♥ {A.short_name(r["b"])}</div>'
                             f'<div class="d">케미 지수 {r["케미 지수"]:.0f} · 서로 답장 {r["주고받은 답장"]}회 · '
                             f'평균 {spd}</div></div>', unsafe_allow_html=True)
            if len(top):
                st.caption(f"👉 1:1 탭에서 **{top.iloc[0]['a']}**·**{top.iloc[0]['b']}** 커플을 골라 정밀 분석해 보세요!")

            st.subheader("🕸️ 누가 누구에게 답할까? — 답장 관계도")
            short = {m: A.short_name(m) for m in G["members"]}
            if len(set(short.values())) < len(short):  # 줄였더니 이름이 겹치면 원래 이름 사용
                short = {m: m for m in G["members"]}
            order = [short[m] for m in G["members"]]
            mat = G["matrix"].reset_index().melt(id_vars="sender", var_name="받은 사람", value_name="답장 수")
            mat = mat.rename(columns={"sender": "답한 사람"})
            mat = mat[mat["답한 사람"] != mat["받은 사람"]]
            mat["답한 사람"] = mat["답한 사람"].map(short)
            mat["받은 사람"] = mat["받은 사람"].map(short)
            vmax = max(int(mat["답장 수"].max()), 1)
            base = alt.Chart(mat).encode(
                x=alt.X("받은 사람:N", sort=order, title="이 사람 말에 →",
                        axis=alt.Axis(orient="top", labelAngle=0, labelFontSize=13, labelFontWeight="bold",
                                      ticks=False, domain=False, labelPadding=8)),
                y=alt.Y("답한 사람:N", sort=order, title="← 이 사람이 답함",
                        axis=alt.Axis(labelFontSize=13, labelFontWeight="bold", ticks=False, domain=False,
                                      labelPadding=8)))
            heat = base.mark_rect(cornerRadius=8, stroke="white", strokeWidth=3).encode(
                color=alt.Color("답장 수:Q", title="답장 수",
                                scale=alt.Scale(range=["#fff4f7", "#ffb3c9", "#ff5c8a", "#c2185b"], domainMin=0)),
                tooltip=["답한 사람", "받은 사람", "답장 수"])
            text = base.mark_text(fontWeight="bold", fontSize=14).encode(
                text="답장 수:Q",
                color=alt.condition(f"datum['답장 수'] >= {vmax * 0.6}", alt.value("white"), alt.value("#5a3a46")))
            n = len(G["members"])
            st.altair_chart((heat + text).properties(height=58 * n + 30, width=110 * n), use_container_width=False)
            st.caption("칸이 진할수록 그 사람 말에 자주(10분 안에) 답했다는 뜻이에요. 대각선은 본인이라 비워뒀어요.")

            st.subheader("📋 멤버별 기록")
            rk = G["rank"].copy()
            rk["메시지 비중"] = rk["메시지"] / rk["메시지"].sum()
            st.dataframe(rk.sort_values("메시지", ascending=False).style.format({
                "메시지": "{:,.0f}", "선톡": "{:,.0f}", "답장 속도(분)": "{:.1f}", "ㅋ/메시지": "{:.2f}",
                "허공 외침": "{:,.0f}", "메시지 비중": "{:.0%}"}), use_container_width=True)

            gdf = G["df"]
            hourly = gdf.groupby(["hour", "sender"]).size().reset_index(name="메시지")
            st.subheader("🕐 시간대별 활동")
            st.altair_chart(alt.Chart(hourly).mark_area(opacity=.8).encode(
                x=alt.X("hour:O", title="시"), y=alt.Y("메시지:Q", stack="zero"),
                color=alt.Color("sender:N", title=""), tooltip=["hour", "sender", "메시지"]
            ).properties(height=300), use_container_width=True)

            # ── 단톡방 결과 카드
            st.subheader("📸 단톡방 결과 카드")
            default_room = "우리 단톡방" if (pseudo or not ROOM) else ROOM
            room = st.text_input("카드에 들어갈 방 이름", default_room, max_chars=20)
            gmin, gmax = gdf["time"].min(), gdf["time"].max()
            period = f"{gmin:%y.%m.%d}~{gmax:%m.%d}"
            pair_list = [(r["a"], r["b"], r["케미 지수"], r["주고받은 답장"]) for _, r in G["pairs"].head(3).iterrows()]
            gpng = group_card_png(room, len(G["members"]), len(gdf), period, G["awards"], pair_list)
            if gpng:
                gc1, gc2 = st.columns([1, 1.4])
                gc1.image(gpng, use_container_width=True)
                with gc2:
                    st.markdown("단톡방에 바로 올리기 좋은 인스타 스토리 사이즈예요.\n\n"
                                "- 방 이름은 위 칸에서 자유롭게 바꿀 수 있어요.\n"
                                "- 멤버 실명이 걱정되면 **가명 처리**를 켜고 받으세요.")
                    st.download_button("⬇️ 단톡방 카드 다운로드 (PNG)", gpng, file_name="group_report.png",
                                       mime="image/png", type="primary", use_container_width=True)
            else:
                st.warning("한글 폰트를 찾지 못해 카드를 만들 수 없어요.")

# ═════════════════════════════════════════════
# 분석 방법 탭
# ═════════════════════════════════════════════
with tab_info:
    st.subheader("🔬 이 분석기는 어떻게 판정하나요?")
    st.markdown(f"""
**1. 마음의 지분 (두 사람 합계 100%)**
관심 있는 사람이 보이는 행동 7가지를 두 사람끼리 비교해서 가중치를 곱해 더했어요.

| 신호 | 가중치 | 해석 |
|---|---|---|
| 선톡 | {A.WEIGHTS['선톡']} | {hours}시간 이상 끊긴 뒤 먼저 말을 건 횟수 |
| 답장 속도 | {A.WEIGHTS['답장 속도']} | 상대 메시지에 답하기까지 걸린 시간의 중앙값 (빠를수록 ↑) |
| 메시지 양 | {A.WEIGHTS['메시지 양']} | 보낸 메시지 수 |
| 글 길이 | {A.WEIGHTS['글 길이']} | 평균 글자 수 (성의) |
| 질문 | {A.WEIGHTS['질문']} | 질문이 포함된 메시지 비율 (궁금함 = 관심) |
| ㅋㅋ | {A.WEIGHTS['ㅋㅋ']} | 메시지당 ㅋ 개수 (리액션) |
| 이모티콘·애정 | {A.WEIGHTS['이모티콘·애정']} | 이모티콘, 사진, 하트, '보고싶다' 등 |

**2. 썸 온도 (0~100°)** — 관계 전체가 얼마나 뜨거운지
하루 메시지 양(30) + 답장 속도(25) + 새벽 대화 비율(15) + 최근 2주 증가세(15) + 애정 표현 빈도(15)

**3. 고백 성공 확률** — 썸 온도 × 0.55 + 마음의 균형(지분이 50:50에 가까울수록 ↑) × 0.30 + 최근 증가세 × 15  
추천 타이밍은 상대가 메시지를 가장 많이 보낸 요일과 시간대예요.

**4. 썸 유형** — 선톡 비율로 직진러 / 밀당러 / 츤데레를 나누고, 가장 두드러진 대화 습관(새벽감성, 칼답, ㅋㅋ폭격 등)을 앞에 붙여요.

**5. 판정**
- 온도 55° 이상 + 지분 차이 7%p 미만 → 💞 쌍방 썸
- 온도 55° 이상 + 한쪽 쏠림 → 🔥 한쪽이 더 달아오름
- 온도 55° 미만 + 균형 → 🧊 미지근한 친구
- 온도 55° 미만 + 한쪽 쏠림 → 💔 짝사랑 경보

**⚠️ 한계**
- 가중치는 "관심 있으면 이럴 것"이라는 상식에 기반한 **재미용 지표**예요. 실제 연애 결과로 검증된 모델이 아니에요.
- 말투가 원래 짧거나 답장이 느린 사람은 실제 마음보다 낮게 나올 수 있어요.
- 카톡 밖(전화, 직접 만남)에서의 관계는 반영되지 않아요.

**🛡️ 개인정보**
- 업로드한 파일은 분석 서버의 메모리에서만 처리되고, 디스크·DB에 저장하거나 외부로 보내지 않아요.
- 이 앱은 대화 내용을 수집하지 않아요. 다만 인터넷에 배포된 서비스이므로 민감한 대화는 올리지 않는 걸 권장해요.
- 전화번호·이메일·링크·긴 숫자는 분석 전에 자동으로 가려져요.
- 가명 처리를 켜면 화면과 결과 카드에 실명이 나오지 않아요.
""")
