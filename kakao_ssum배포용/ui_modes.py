"""
ui_modes.py — 친구 모드 / 팀플 모드 화면
(썸 모드는 app.py 본문에 있음)
"""

import altair as alt
import pandas as pd
import streamlit as st

import analyzer as A
from share_card import make_friend_card, make_friend_group_card, make_team_card

CACHE_VER = "v5"
MINT, SUN, SKY, RED, ORANGE = "#16aa8c", "#f0a014", "#3c78ff", "#f04650", "#fa9a3c"


# ───────────── 캐시 ─────────────
@st.cache_data(show_spinner=False)
def _friend_pair(df, a, b, hours, ver=CACHE_VER):
    return A.analyze_friend_pair(df, a, b, hours)


@st.cache_data(show_spinner=False)
def _friend_group(df, ver=CACHE_VER):
    return A.analyze_friend_group(df)


@st.cache_data(show_spinner=False)
def _team(df, ver=CACHE_VER):
    return A.analyze_team(df)


@st.cache_data(show_spinner=False)
def _png(kind, *args, ver=CACHE_VER):
    fn = {"friend": make_friend_card, "squad": make_friend_group_card, "team": make_team_card}[kind]
    return fn(*args)


# ───────────── 공통 조각 ─────────────
def _html(s):
    st.markdown(" ".join(line.strip() for line in s.splitlines()), unsafe_allow_html=True)


def _verdict(emoji, title, desc, c1, c2, border):
    _html(f"""
    <div class="card" style="background:linear-gradient(135deg,{c1},{c2});border-color:{border}">
      <div class="verdict-emoji">{emoji}</div>
      <div class="verdict" style="color:{border}">{title}</div>
      <div class="verdict-sub">{desc}</div>
    </div>""")


def _tiles(items, color, soft, cols=3):
    """items=[(emoji, 제목, 이름, 설명)]"""
    cs = st.columns(cols)
    for i, (e, t, who, d) in enumerate(items):
        cs[i % cols].markdown(
            f'<div class="award" style="background:{soft};border-color:{color}33;margin-bottom:.7rem">'
            f'<div class="e">{e}</div><div class="n" style="color:{color}">{t}</div>'
            f'<div style="font-size:1.25rem;font-weight:800">{A.short_name(who)}</div>'
            f'<div class="d">{d}</div></div>', unsafe_allow_html=True)


def _highlights(hl, color):
    c1, c2 = st.columns(2)
    for i, (e, t, d) in enumerate(hl):
        (c1 if i % 2 == 0 else c2).markdown(
            f'<div class="hl">{e} <b style="color:{color}">{t}</b><br>{d}</div>', unsafe_allow_html=True)


def _card_block(png, fname, label, notes):
    if not png:
        st.warning("한글 폰트를 찾지 못해 카드를 만들 수 없어요. `fonts/` 폴더를 확인해 주세요.")
        return
    c1, c2 = st.columns([1, 1.4])
    c1.image(png, use_container_width=True)
    with c2:
        st.markdown("인스타 스토리 사이즈(1080×1920)예요.\n\n" + "\n".join(f"- {n}" for n in notes))
        st.download_button(f"⬇️ {label} 다운로드 (PNG)", png, file_name=fname, mime="image/png",
                           type="primary", use_container_width=True)


def _period(df):
    return f"{df['time'].min():%y.%m.%d}~{df['time'].max():%m.%d}"


def _room_input(room, pseudo, key, default):
    d = default if (pseudo or not room) else room
    return st.text_input("카드에 들어갈 방 이름", d, max_chars=20, key=key)


def _share_bar(a, b, pa, ca, cb):
    _html(f"""
    <div style="display:flex;height:46px;border-radius:23px;overflow:hidden;font-weight:700;color:white">
      <div style="width:{pa:.1f}%;background:{ca};display:flex;align-items:center;justify-content:center">{a} {pa:.0f}%</div>
      <div style="width:{100 - pa:.1f}%;background:{cb};display:flex;align-items:center;justify-content:center">{b} {100 - pa:.0f}%</div>
    </div>""")


# ═════════════════════════════════════════════
# 친구 모드
# ═════════════════════════════════════════════
def render_friend(df_all, room, pseudo, hours):
    senders = df_all["sender"].value_counts()
    is_group = len(senders) > 2
    names = ["👯 1:1 우정 분석"] + (["👥 단톡방 우정"] if is_group else []) + ["ℹ️ 분석 방법"]
    tabs = st.tabs(names)

    # ── 1:1
    with tabs[0]:
        ns = senders.index.tolist()
        if is_group:
            st.caption("단톡방이에요. 분석할 두 사람을 골라주세요. (👥 탭에서 '베프 짝꿍'을 먼저 확인해 보세요!)")
        c1, c2 = st.columns(2)
        a = c1.selectbox("🙋 나", ns, index=0, key="fa")
        b = c2.selectbox("👯 친구", [s for s in ns if s != a], index=0, key="fb")
        with st.spinner("우정을 측정하는 중... 👯"):
            R = _friend_pair(df_all, a, b, hours)
        S = R["stats"]

        _verdict(R["emoji"], R["title"], R["desc"], "#e9fbf5", "#fff8e1", MINT)
        if R["emoji"] == "💎":
            st.balloons()
        if R["warn"]:
            st.warning("🚨 우정 위기 감지 — " + R["warn"])

        st.write("")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("🌡️ 우정 온도", f"{R['temp']:.0f}°")
        m2.metric("📅 꾸준함", f"{R['consistency']:.0%}", help="대화한 주 / 전체 기간(주)")
        m3.metric(f"💛 {b}님이 챙기는 비율", f"{100 - R['score_a']:.0f}%", f"{(100 - R['score_a']) - 50:+.0f}%p vs 반반")
        trend = "📈 늘어나는 중" if R["trend"] > 0.1 else ("📉 줄어드는 중" if R["trend"] < -0.1 else "➡️ 유지")
        m4.metric("최근 2주 흐름", trend, f"{R['recent'] - R['prev']:+d}개")

        st.subheader("🧬 우리의 우정 유형")
        t1, t2 = st.columns(2)
        for col, p, c, soft in ((t1, a, MINT, "#e2f8f1"), (t2, b, SUN, "#fff5d6")):
            tp, td = R["types"][p]
            col.markdown(f'<div class="card" style="background:{soft};border-color:{c}55">'
                         f'<div style="color:{c};font-weight:700">{p}</div>'
                         f'<div style="font-size:1.7rem;font-weight:800">{tp}</div>'
                         f'<div style="color:#666">{td}</div></div>', unsafe_allow_html=True)

        st.subheader("💛 누가 더 챙길까?")
        _share_bar(a, b, R["score_a"], MINT, SUN)
        bd = pd.DataFrame([{"항목": f"{k} ({A.FRIEND_WEIGHTS[k]}점)", "사람": p, "비율": v if p == a else 1 - v}
                           for k, v in R["parts"].items() for p in (a, b)])
        st.altair_chart(alt.Chart(bd).mark_bar().encode(
            y=alt.Y("항목:N", sort=None, title=None),
            x=alt.X("비율:Q", stack="normalize", axis=alt.Axis(format="%"), title=None),
            color=alt.Color("사람:N", title="", scale=alt.Scale(domain=[a, b], range=[MINT, SUN])),
            tooltip=["항목", "사람", alt.Tooltip("비율:Q", format=".0%")]).properties(height=220),
            use_container_width=True)

        st.subheader("🎬 우리의 명장면")
        _highlights(R["highlights"], MINT)

        df = R["df"]
        color = alt.Color("sender:N", title="", scale=alt.Scale(domain=[a, b], range=[MINT, SUN]))
        x1, x2, x3 = st.tabs(["📅 주별 대화량", "🕐 시간대", "🔤 말버릇"])
        with x1:
            wk = df.assign(주=df["time"].dt.to_period("W").dt.start_time).groupby(["주", "sender"]).size()
            wk = wk.reset_index(name="메시지")
            st.altair_chart(alt.Chart(wk).mark_area(opacity=.75, interpolate="monotone").encode(
                x=alt.X("주:T", title=None), y=alt.Y("메시지:Q", stack="zero"), color=color,
                tooltip=["주:T", "sender", "메시지"]).properties(height=300), use_container_width=True)
        with x2:
            hourly = df.groupby(["hour", "sender"]).size().reset_index(name="메시지")
            st.altair_chart(alt.Chart(hourly).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
                x=alt.X("hour:O", title="시"), y="메시지:Q", color=color, xOffset="sender:N").properties(height=300),
                use_container_width=True)
        with x3:
            w1, w2 = st.columns(2)
            for col, p, c in ((w1, a, MINT), (w2, b, SUN)):
                w = pd.DataFrame(R["words"][p], columns=["단어", "횟수"])
                col.markdown(f"**{p}**의 말버릇")
                if len(w):
                    col.altair_chart(alt.Chart(w).mark_bar(color=c, cornerRadiusEnd=4).encode(
                        y=alt.Y("단어:N", sort="-x", title=None), x="횟수:Q").properties(height=320),
                        use_container_width=True)

        st.subheader("📊 상세 비교")
        keys = ["메시지 수", "선톡 횟수", "약속 제안", "챙기는 말", "드립·찐반응", "진지한 대화", "답장 속도(분, 중앙값)", "ㅋ 개수"]
        rows = []
        for k in keys:
            row = {"항목": k}
            for p in (a, b):
                v = S[p][k]
                row[p] = ("-" if pd.isna(v) else f"{v:.1f}분") if k.startswith("답장") else f"{int(v):,}"
            rows.append(row)
        st.dataframe(pd.DataFrame(rows).set_index("항목"), use_container_width=True)

        st.subheader("📸 우정 카드 공유하기")
        png = _png("friend", a, b, R["title"], R["desc"], R["temp"], R["consistency"], R["score_a"], S,
                   R["types"][a], R["types"][b])
        _card_block(png, "friend_report.png", "우정 카드", ["친구한테 보내면 반응 보장 😆", "이름이 걱정되면 **가명 처리**를 켜고 받으세요."])

    # ── 단톡방
    if is_group:
        with tabs[1]:
            F = _friend_group(df_all)
            if len(F["members"]) < 3:
                st.info("메시지를 3개 이상 보낸 사람이 3명 미만이라 단톡방 분석이 어려워요.")
            else:
                c1, c2 = st.columns([1, 2])
                with c1:
                    _html(f"""
                    <div class="card" style="text-align:center;background:linear-gradient(135deg,#e9fbf5,#fff8e1);border-color:{MINT}55">
                      <div style="color:{MINT};font-weight:700">🫀 단톡 생존율</div>
                      <div style="font-size:3.4rem;font-weight:900;color:{MINT};line-height:1.1">{F['survival']:.0f}%</div>
                      <div style="font-weight:700">{F['survival_label']}</div>
                      <div style="color:#888;font-size:.85rem;margin-top:.3rem">최근 2주 {F['recent']}개 · 직전 2주 {F['prev']}개 ·
                      최근 활동 멤버 {F['active_share']:.0%}</div>
                    </div>""")
                with c2:
                    st.markdown("#### 👯 베프 짝꿍 TOP 3")
                    top = F["pairs"].head(3)
                    pc = st.columns(3)
                    for i, (col, (_, r)) in enumerate(zip(pc, top.iterrows())):
                        col.markdown(
                            f'<div class="award" style="background:#f2fbf8;border-color:{MINT}33">'
                            f'<div class="e">{["🥇", "🥈", "🥉"][i]}</div>'
                            f'<div class="n">{A.short_name(r["a"])} & {A.short_name(r["b"])}</div>'
                            f'<div class="d">케미 {r["케미 지수"]:.0f} · 서로 답장 {r["주고받은 답장"]}회</div></div>',
                            unsafe_allow_html=True)

                st.subheader("🎭 우리 단톡방 역할")
                _tiles(F["roles"], MINT, "#f2fbf8", cols=3)

                st.subheader("📈 단톡방 맥박 — 주별 대화량")
                gdf = F["df"]
                wk = gdf.assign(주=gdf["time"].dt.to_period("W").dt.start_time,
                                이름=gdf["sender"].map(A.short_name)).groupby(["주", "이름"]).size().reset_index(name="메시지")
                st.altair_chart(alt.Chart(wk).mark_area(opacity=.85, interpolate="monotone").encode(
                    x=alt.X("주:T", title=None), y=alt.Y("메시지:Q", stack="zero"),
                    color=alt.Color("이름:N", title="", scale=alt.Scale(scheme="tealblues")),
                    tooltip=["주:T", "이름", "메시지"]).properties(height=300), use_container_width=True)

                st.subheader("📸 단톡방 카드")
                rn = _room_input(room, pseudo, "squad_room", "우리 단톡방")
                pairs = [(r["a"], r["b"], float(r["케미 지수"]), int(r["주고받은 답장"])) for _, r in top.iterrows()]
                png = _png("squad", rn, len(F["members"]), len(gdf), _period(gdf), pairs, F["roles"],
                           float(F["survival"]), F["survival_label"])
                _card_block(png, "squad_report.png", "단톡방 카드", ["단톡방에 바로 올려보세요 🎉"])

    with tabs[-1]:
        st.markdown(f"""
#### 👯 친구 모드는 이렇게 계산해요
**누가 더 챙길까 (합계 100%)** — 선톡 {A.FRIEND_WEIGHTS['선톡']} · 약속 제안 {A.FRIEND_WEIGHTS['약속 제안']} ·
챙기는 말 {A.FRIEND_WEIGHTS['챙기는 말']} · 답장 속도 {A.FRIEND_WEIGHTS['답장 속도']} · 리액션 {A.FRIEND_WEIGHTS['리액션(ㅋ)']}

**우정 온도 (0~100°)** — 꾸준함(대화한 주 비율) 30 + 대화량 20 + 웃음(ㅋ) 20 + 진지한 대화 15 + 최근 증가세 15

**판정** — 💎 평생 베프(온도 60↑, 균형) · 🐶 한쪽이 더 챙기는 베프 · 🍻 놀 때 부르는 친구 · 📞 용건만 친구 · 🌫️ 연락 끊기기 직전

**단톡 생존율** — 최근 2주 대화량 변화 + 최근 활동한 멤버 비율

※ 재미용 지표예요. 연락이 뜸해도 진짜 친구는 진짜 친구입니다 🫶
""")


# ═════════════════════════════════════════════
# 팀플 모드
# ═════════════════════════════════════════════
def render_team(df_all, room, pseudo):
    tabs = st.tabs(["🛠️ 팀플 분석", "ℹ️ 분석 방법"])
    with tabs[0]:
        R = _team(df_all)
        T = R["table"]
        if len(R["members"]) < 2:
            st.info("메시지를 3개 이상 보낸 사람이 2명 이상이어야 해요.")
            return
        e, tt, td = R["type"]
        _verdict(e, tt, td, "#eef3ff", "#e8fbff", SKY)

        st.write("")
        sus, sv = R["suspect"], float(T.loc[R["suspect"], "무임승차 지수"])
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("👥 팀원", f"{len(R['members'])}명")
        m2.metric("💼 업무 대화 비율", f"{R['df']['work'].mean():.0%}")
        m3.metric("🏆 MVP", A.short_name(R["mvp"]), f"기여도 {T.loc[R['mvp'], '기여도']:.0f}")
        m4.metric("🚨 무임승차 의심", A.short_name(sus) if sv >= 50 else "없음",
                  f"{sv:.0f}%" if sv >= 50 else None, delta_color="inverse")

        st.subheader("🏅 팀원별 역할과 판정")
        cols = st.columns(min(len(T), 3))
        for i, (m, r) in enumerate(T.iterrows()):
            fr = float(r["무임승차 지수"])
            c = RED if fr >= 70 else (ORANGE if fr >= 50 else SKY)
            cols[i % len(cols)].markdown(
                f'<div class="award" style="background:#f5f8ff;border-color:{c}55;margin-bottom:.7rem;text-align:left;padding:1rem 1.2rem">'
                f'<div style="display:flex;justify-content:space-between;align-items:center">'
                f'<span style="font-size:1.35rem;font-weight:800">{A.short_name(m)}</span>'
                f'<span style="color:{SKY};font-weight:800">기여도 {r["기여도"]:.0f}</span></div>'
                f'<div style="font-weight:700;margin:.2rem 0">{r["역할"]}</div>'
                f'<div style="background:#e6ecfa;border-radius:8px;height:10px;margin:.4rem 0">'
                f'<div style="width:{r["기여도"]:.0f}%;background:{c};height:10px;border-radius:8px"></div></div>'
                f'<div style="color:{c};font-weight:700;font-size:.9rem">{r["판정"]} · 의심 지수 {fr:.0f}%</div></div>',
                unsafe_allow_html=True)

        st.subheader("📊 기여도는 어디서 나왔을까?")
        parts = R["parts"].copy()
        parts.index = [A.short_name(i) for i in parts.index]
        long = parts.reset_index(names="팀원").melt(id_vars="팀원", var_name="항목", value_name="점수")
        order = [A.short_name(m) for m in T.index]
        st.altair_chart(alt.Chart(long).mark_bar(cornerRadiusEnd=3).encode(
            y=alt.Y("팀원:N", sort=order, title=None, axis=alt.Axis(labelFontSize=13, labelFontWeight="bold")),
            x=alt.X("점수:Q", title="기여도 (100점 만점)", scale=alt.Scale(domain=[0, 100])),
            color=alt.Color("항목:N", title="", scale=alt.Scale(
                domain=list(A.TEAM_WEIGHTS), range=["#3c78ff", "#20c0a0", "#f0a014", "#8a5cff", "#ff6b8a"])),
            order=alt.Order("항목:N"),
            tooltip=["팀원", "항목", alt.Tooltip("점수:Q", format=".1f")]).properties(height=55 * len(order) + 40),
            use_container_width=True)

        st.subheader("⏰ 마감 텐션 그래프")
        daily = R["daily"].copy()
        base = alt.Chart(daily).encode(x=alt.X("date:T", title=None))
        bars = base.mark_bar(color="#c9d8ff", cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
            y=alt.Y("메시지:Q", title="하루 메시지"), tooltip=["date:T", "메시지", "업무"])
        line = base.mark_line(color=SKY, strokeWidth=3, point=True).encode(y="업무:Q")
        st.altair_chart((bars + line).properties(height=280), use_container_width=True)
        st.caption("막대 = 전체 메시지, 파란 선 = 업무 메시지. 마감 직전에 선이 치솟는 건… 다들 아시죠 😇")

        st.subheader("🎬 팀플 명장면")
        _highlights(R["highlights"], SKY)

        with st.expander("📋 팀원별 상세 기록"):
            show = T.drop(columns=["판정", "역할"]).copy()
            show.index = [A.short_name(i) for i in show.index]
            st.dataframe(show.style.format({
                "메시지": "{:,.0f}", "업무 대화": "{:,.0f}", "완료 보고": "{:,.0f}", "자료 공유": "{:,.0f}",
                "주도(회의·분담)": "{:,.0f}", "호출 응답률": "{:.0%}", "'넵' 비율": "{:.0%}", "질문": "{:,.0f}",
                "ㅋ/메시지": "{:.2f}", "답장 속도(분)": "{:.1f}", "야근 메시지": "{:,.0f}", "기여도": "{:.0f}",
                "무임승차 지수": "{:.0f}"}), use_container_width=True)

        st.subheader("📸 팀플 결과 카드")
        rn = _room_input(room, pseudo, "team_room", "우리 팀플방")
        rows = [(m, str(r["역할"]), float(r["기여도"]), float(r["무임승차 지수"])) for m, r in T.iterrows()]
        png = _png("team", rn, len(R["members"]), len(R["df"]), _period(R["df"]), R["type"], rows, (sus, sv))
        _card_block(png, "team_report.png", "팀플 카드",
                    ["팀플 끝나고 단톡방에 올리면 웃음 보장 (싸움 주의 ⚠️)", "이름이 걱정되면 **가명 처리**를 켜고 받으세요."])

    with tabs[1]:
        w = A.TEAM_WEIGHTS
        st.markdown(f"""
#### 🛠️ 팀플 모드는 이렇게 계산해요
**기여도 (100점)** — 항목마다 팀에서 제일 많이 한 사람을 만점으로 두고 비율을 매겨요.
업무 대화 {w['업무 대화']} · 완료 보고 {w['완료 보고']} · 자료 공유 {w['자료 공유']} · 주도(회의·분담) {w['주도(회의·분담)']} · 호출 응답률 {w['호출 응답률']}

- **업무 대화**: 자료, 발표, PPT, 수정, 마감 같은 단어가 들어간 메시지
- **완료 보고**: "했어요", "올렸습니다", "수정했어요" 등
- **자료 공유**: 파일, 링크, 사진
- **주도**: "회의", "역할 분담", "~해주세요", "다들 ~ 가능?" 등
- **호출 응답률**: 누가 회의·분담 얘기를 꺼낸 뒤 1시간 안에 반응한 비율

**무임승차 지수** — (100 − 기여도) × 0.75 + "넵·네·확인"만 하는 비율 × 25

**팀 유형** — 기여도가 얼마나 고르게 나뉘었는지(지니계수)와 1등의 비중으로 판정해요.

⚠️ 카톡 밖(노션, 깃허브, 대면 회의)에서 한 일은 반영되지 않아요. **재미로만** 봐주시고, 이걸로 싸우지 마세요 🙏
""")
