"""
share_card.py — 인스타 스토리(1080x1920) 비율 결과 카드 PNG 생성
한글 폰트를 OS별 기본 경로에서 자동으로 찾습니다.
fonts/ 폴더에 .ttf/.otf를 넣어두면 그걸 우선 사용합니다.
"""

import glob
import io
import math
import os
import re

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_CANDIDATES = [
    *sorted(glob.glob(os.path.join(HERE, "fonts", "*.[ot]tf"))),
    # Windows
    "C:/Windows/Fonts/malgunbd.ttf", "C:/Windows/Fonts/malgun.ttf",
    # macOS
    "/System/Library/Fonts/AppleSDGothicNeo.ttc", "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
    "/Library/Fonts/AppleGothic.ttf",
    # Linux / Streamlit Cloud (packages.txt 에 fonts-nanum)
    "/usr/share/fonts/truetype/nanum/NanumGothicExtraBold.ttf", "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
]


def find_font():
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    # 마지막 수단: 시스템 폰트 폴더에서 한글 폰트 이름으로 검색
    for pat in ("*Nanum*", "*CJK*KR*", "*CJK*", "*malgun*", "*Gothic*"):
        for root in ("/usr/share/fonts", "/usr/local/share/fonts", "C:/Windows/Fonts", "/Library/Fonts"):
            hits = glob.glob(os.path.join(root, "**", pat), recursive=True)
            hits = [h for h in hits if h.lower().endswith((".ttf", ".otf", ".ttc"))]
            if hits:
                return sorted(hits)[0]
    return None


FONT_PATH = find_font()
RE_EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200d]")


def _f(size):
    return ImageFont.truetype(FONT_PATH, size)


def _clean(s):
    return RE_EMOJI.sub("", str(s)).strip()


def _center(draw, y, text, font, fill):
    w = draw.textlength(text, font=font)
    draw.text(((1080 - w) / 2, y), text, font=font, fill=fill)


def _wrap(draw, text, font, max_w):
    lines, cur = [], ""
    for ch in text:
        if draw.textlength(cur + ch, font=font) > max_w and cur:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def make_card(a, b, title, desc, temp, score_a, stats, badges_a, badges_b):
    """결과 카드 PNG bytes 반환 (폰트가 없으면 None)"""
    if FONT_PATH is None:
        return None
    W, H = 1080, 1920
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    top, bottom = (255, 92, 138), (255, 196, 160)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3)))

    # 배경 하트 장식
    for x, y, r in [(110, 250, 50), (960, 170, 70), (930, 1840, 45), (120, 1830, 40)]:
        d.text((x - r, y - r), "♥", font=_f(r * 2), fill=(255, 214, 226))

    WHITE, DARK, PINK, BLUE = (255, 255, 255), (60, 40, 50), (255, 92, 138), (92, 138, 255)
    _center(d, 120, "KAKAOTALK SSUM REPORT", _f(40), WHITE)
    _center(d, 190, f"{_clean(a)}  ♥  {_clean(b)}", _f(64), WHITE)

    # 메인 카드
    d.rounded_rectangle((70, 320, 1010, 1780), radius=50, fill=WHITE)
    _center(d, 380, "썸 판정", _f(38), (170, 140, 150))
    _center(d, 440, _clean(title), _f(84), PINK)
    y = 560
    for line in _wrap(d, _clean(desc), _f(40), 820)[:3]:
        _center(d, y, line, _f(40), DARK)
        y += 56

    # 썸 온도
    _center(d, 740, "썸 온도", _f(38), (170, 140, 150))
    _center(d, 790, f"{temp:.0f}°", _f(130), DARK)
    d.rounded_rectangle((170, 960, 910, 990), radius=15, fill=(255, 228, 236))
    d.rounded_rectangle((170, 960, 170 + 740 * min(temp, 100) / 100, 990), radius=15, fill=PINK)

    # 마음의 지분
    _center(d, 1040, "마음의 지분", _f(38), (170, 140, 150))
    x0, x1, yb = 130, 950, 1100
    split = x0 + (x1 - x0) * score_a / 100
    d.rounded_rectangle((x0, yb, x1, yb + 80), radius=40, fill=PINK)
    d.rounded_rectangle((x0, yb, max(split, x0 + 80), yb + 80), radius=40, fill=BLUE)
    if split - x0 > 80:
        d.rectangle((split - 40, yb, split, yb + 80), fill=BLUE)
    fa, fb = f"{_clean(a)} {score_a:.0f}%", f"{_clean(b)} {100 - score_a:.0f}%"
    d.text((x0 + 30, yb + 18), fa, font=_f(38), fill=WHITE)
    d.text((x1 - 30 - d.textlength(fb, font=_f(38)), yb + 18), fb, font=_f(38), fill=WHITE)

    # 핵심 수치
    sa, sb = stats[a], stats[b]
    rows = [("선톡", f"{sa['선톡 횟수']}회", f"{sb['선톡 횟수']}회"),
            ("답장 속도", _rep(sa), _rep(sb)),
            ("메시지", f"{sa['메시지 수']:,}개", f"{sb['메시지 수']:,}개")]
    y = 1240
    for label, va, vb in rows:
        _center(d, y, label, _f(34), (170, 140, 150))
        d.text((170, y - 4), va, font=_f(42), fill=BLUE)
        d.text((910 - d.textlength(vb, font=_f(42)), y - 4), vb, font=_f(42), fill=PINK)
        y += 80

    # 뱃지
    _center(d, 1510, "획득한 칭호", _f(34), (170, 140, 150))
    y = 1570
    for who, bl, col in ((a, badges_a, BLUE), (b, badges_b, PINK)):
        names = " · ".join(_clean(n) for _, n, _ in bl[:3])
        text = f"{_clean(who)}  {names}"
        for line in _wrap(d, text, _f(36), 840)[:2]:
            _center(d, y, line, _f(36), col)
            y += 50
        y += 20

    _center(d, 1820, "재미로 보는 분석 · 카톡 썸 분석기", _f(32), WHITE)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def make_group_card(room, n_members, n_msgs, period, awards, pairs):
    """단톡방 결과 카드. awards=[(emoji,상,이름,설명)], pairs=[(a,b,케미지수,답장수)]"""
    if FONT_PATH is None:
        return None
    W, H = 1080, 1920
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    top, bottom = (120, 110, 255), (255, 140, 180)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3)))
    for x, y, r in [(110, 250, 50), (960, 170, 70), (930, 1840, 45), (120, 1830, 40)]:
        d.text((x - r, y - r), "♥", font=_f(r * 2), fill=(235, 225, 255))

    WHITE, DARK, GREY, PINK, PURPLE = (255, 255, 255), (60, 40, 50), (160, 150, 170), (255, 92, 138), (120, 110, 255)
    _center(d, 110, "KAKAOTALK GROUP REPORT", _f(40), WHITE)
    title = _clean(room) or "우리 단톡방"
    _center(d, 175, _wrap(d, title, _f(62), 900)[0], _f(62), WHITE)
    _center(d, 260, f"{n_members}명 · 메시지 {n_msgs:,}개 · {period}", _f(34), WHITE)

    d.rounded_rectangle((70, 340, 1010, 1780), radius=50, fill=WHITE)

    # 어워즈
    _center(d, 390, "단톡방 어워즈", _f(44), PURPLE)
    y = 470
    for _, name, who, desc in awards[:5]:
        d.rounded_rectangle((130, y, 950, y + 100), radius=50, fill=(245, 242, 255))
        d.text((175, y + 26), _clean(name), font=_f(40), fill=GREY)
        wtxt = _clean(who)
        d.text((905 - d.textlength(wtxt, font=_f(46)), y + 20), wtxt, font=_f(46), fill=DARK)
        y += 120

    # 썸 의심 커플
    y += 30
    _center(d, y, "썸 의심 커플 TOP 3", _f(44), PINK)
    y += 80
    for i, (a, b, chem, n) in enumerate(pairs[:3]):
        rank = f"{i + 1}위"
        d.text((150, y + 4), rank, font=_f(40), fill=PINK if i == 0 else GREY)
        couple = f"{_clean(a)} ♥ {_clean(b)}"
        d.text((270, y), couple, font=_f(48 if i == 0 else 42), fill=DARK)
        meta = f"케미 {chem:.0f}"
        d.text((930 - d.textlength(meta, font=_f(34)), y + 8), meta, font=_f(34), fill=GREY)
        y += 115
    if pairs:
        a, b, chem, n = pairs[0]
        _center(d, y + 10, f"{_clean(a)}·{_clean(b)}, 서로에게 {int(n)}번이나 바로 답장했어요", _f(34), PINK)

    _center(d, 1690, "케미 지수 = 서로에게 10분 안에 답한 비율", _f(30), GREY)
    _center(d, 1820, "재미로 보는 분석 · 카톡 썸 분석기", _f(32), WHITE)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _rep(s):
    r = s["답장 속도(분, 중앙값)"]
    return "-" if (r is None or (isinstance(r, float) and math.isnan(r))) else f"{r:.0f}분"
