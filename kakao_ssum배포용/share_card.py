"""
share_card.py — 인스타 스토리(1080x1920) 결과 카드 PNG 생성
fonts/ 폴더의 한글 폰트를 우선 사용하고, 없으면 OS 기본 폰트를 찾습니다.
"""

import glob
import io
import math
import os
import re

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_CANDIDATES = [
    *sorted(glob.glob(os.path.join(HERE, "fonts", "*.[ot]tf"))),
    "C:/Windows/Fonts/malgunbd.ttf", "C:/Windows/Fonts/malgun.ttf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc", "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf", "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
]


def find_font():
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    for pat in ("*Nanum*", "*CJK*KR*", "*CJK*", "*malgun*", "*Gothic*"):
        for root in ("/usr/share/fonts", "/usr/local/share/fonts", "C:/Windows/Fonts", "/Library/Fonts"):
            hits = [h for h in glob.glob(os.path.join(root, "**", pat), recursive=True)
                    if h.lower().endswith((".ttf", ".otf", ".ttc"))]
            if hits:
                return sorted(hits)[0]
    return None


FONT_PATH = find_font()
RE_EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u2664\u2666-\u27BF\uFE0F\u200d]")
_FONT_CACHE = {}

W, H = 1080, 1920
WHITE = (255, 255, 255)
INK = (45, 30, 40)
MUTED = (165, 135, 150)
PINK = (255, 79, 129)
PINK_SOFT = (255, 236, 242)
BLUE = (88, 128, 255)
BLUE_SOFT = (236, 242, 255)


# ─────────────── 헬퍼 ───────────────
def _f(size):
    size = int(size)
    if size not in _FONT_CACHE:
        _FONT_CACHE[size] = ImageFont.truetype(FONT_PATH, size)
    return _FONT_CACHE[size]


def _clean(s):
    return RE_EMOJI.sub("", str(s)).strip()


def _short(name):
    s = re.sub(r"\s*[\(\[（【].*?[\)\]）】]\s*", "", _clean(name)).strip()
    return s or _clean(name)


def _fit(d, text, max_w, size, min_size=22):
    while size > min_size and d.textlength(text, font=_f(size)) > max_w:
        size -= 2
    return _f(size)


def _wrap(d, text, font, max_w):
    """띄어쓰기 단위 줄바꿈 (한 단어가 너무 길면 글자 단위)"""
    lines, cur = [], ""
    for word in text.split(" "):
        trial = f"{cur} {word}".strip()
        if d.textlength(trial, font=font) <= max_w:
            cur = trial
            continue
        if cur:
            lines.append(cur)
        cur = ""
        for ch in word:
            if d.textlength(cur + ch, font=font) > max_w and cur:
                lines.append(cur)
                cur = ch
            else:
                cur += ch
    if cur:
        lines.append(cur)
    return lines


def _ct(d, cx, y, text, font, fill):
    """가로 중앙 정렬(cx 기준) 텍스트"""
    d.text((cx - d.textlength(text, font=font) / 2, y), text, font=font, fill=fill)


def _pill(d, cx, y, text, font, fg, bg, pad_x=28, pad_y=14):
    w = d.textlength(text, font=font)
    h = font.size
    d.rounded_rectangle((cx - w / 2 - pad_x, y, cx + w / 2 + pad_x, y + h + pad_y * 2), radius=(h + pad_y * 2) / 2, fill=bg)
    d.text((cx - w / 2, y + pad_y - h * 0.12), text, font=font, fill=fg)
    return y + h + pad_y * 2


def _background(c1, c2):
    """대각선 그라데이션 + 흐릿한 빛 번짐"""
    grad = Image.new("RGB", (W, H))
    g = ImageDraw.Draw(grad)
    for y in range(H):
        t = y / H
        g.line([(0, y), (W, y)], fill=tuple(int(c1[i] * (1 - t) + c2[i] * t) for i in range(3)))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for (x, y, r, col) in [(120, 180, 330, (255, 255, 255, 90)), (980, 520, 280, (255, 220, 120, 70)),
                           (60, 1500, 300, (255, 255, 255, 60)), (1000, 1800, 360, (255, 120, 200, 80))]:
        gd.ellipse((x - r, y - r, x + r, y + r), fill=col)
    glow = glow.filter(ImageFilter.GaussianBlur(110))
    img = grad.convert("RGBA")
    img.alpha_composite(glow)
    return img


def _panel(img, box, radius=56):
    """그림자 있는 흰 패널"""
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((box[0], box[1] + 24, box[2], box[3] + 24), radius=radius, fill=(120, 20, 60, 70))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(28)))
    ImageDraw.Draw(img).rounded_rectangle(box, radius=radius, fill=WHITE)


def _ring(img, cx, cy, r, width, pct, color, track=(255, 230, 238)):
    """안티앨리어싱 원형 게이지 (3배 크게 그린 뒤 축소)"""
    S = 3
    size = (r * 2 + 8) * S
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    bb = (4 * S, 4 * S, size - 4 * S, size - 4 * S)
    ld.arc(bb, 0, 360, fill=track, width=width * S)
    end = -90 + 360 * max(0, min(pct, 100)) / 100
    if pct > 0:
        ld.arc(bb, -90, end, fill=color, width=width * S)
        # 둥근 끝
        rr = (size - 8 * S) / 2 - width * S / 2
        for ang in (-90, end):
            x = size / 2 + rr * math.cos(math.radians(ang))
            y = size / 2 + rr * math.sin(math.radians(ang))
            ld.ellipse((x - width * S / 2, y - width * S / 2, x + width * S / 2, y + width * S / 2), fill=color)
    layer = layer.resize((r * 2 + 8, r * 2 + 8), Image.LANCZOS)
    img.alpha_composite(layer, (int(cx - r - 4), int(cy - r - 4)))


def _png(img):
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _rep(s):
    r = s["답장 속도(분, 중앙값)"]
    return "-" if (r is None or (isinstance(r, float) and math.isnan(r))) else f"{r:.0f}분"


# ─────────────── 1:1 카드 ───────────────
def make_card(a, b, title, desc, temp, score_a, stats, couple, type_a, type_b, prob, when):
    """couple=(커플명, 설명), type_a/b=(유형, 설명), prob=고백 확률, when='금요일 밤 10시'"""
    if FONT_PATH is None:
        return None
    img = _background((255, 94, 141), (255, 176, 134))
    d = ImageDraw.Draw(img)
    sa_, sb_ = _short(a), _short(b)
    cx = W / 2

    # 헤더
    _pill(d, cx, 92, "KAKAOTALK  SSUM  REPORT", _f(26), WHITE, (255, 140, 170), 26, 12)
    head = f"{sa_}  ♥  {sb_}"
    _ct(d, cx, 170, head, _fit(d, head, 900, 76), WHITE)

    # 패널
    _panel(img, (60, 300, 1020, 1790))
    d = ImageDraw.Draw(img)

    # 커플 유형 + 판정
    y = _pill(d, cx, 350, _clean(couple[0]), _fit(d, _clean(couple[0]), 700, 34), PINK, PINK_SOFT, 30, 14)
    _ct(d, cx, y + 22, _clean(title), _fit(d, _clean(title), 860, 92), INK)
    desc = _clean(desc).replace(_clean(a), sa_).replace(_clean(b), sb_)
    yy = y + 150
    for line in _wrap(d, desc, _f(36), 820)[:2]:
        _ct(d, cx, yy, line, _f(36), MUTED)
        yy += 50

    # 두 개의 원형 게이지
    gy = 830
    for gx, pct, big, cap, col in ((310, temp, f"{temp:.0f}°", "썸 온도", PINK),
                                   (770, prob, f"{prob:.0f}%", "고백 성공 확률", (255, 145, 60))):
        _ring(img, gx, gy, 150, 26, pct, col)
        d = ImageDraw.Draw(img)
        _ct(d, gx, gy - 58, big, _f(84), INK)
        _ct(d, gx, gy + 44, cap, _f(30), MUTED)
    y = gy + 190
    y = _pill(d, cx, y, f"추천 고백 타이밍  ·  {_clean(when)}", _fit(d, f"추천 고백 타이밍  ·  {_clean(when)}", 760, 34),
              (230, 110, 30), (255, 241, 228), 30, 14)

    # 마음의 지분
    y += 50
    _ct(d, cx, y, "마음의 지분", _f(30), MUTED)
    y += 54
    x0, x1, bh = 120, 960, 74
    split = x0 + (x1 - x0) * score_a / 100
    d.rounded_rectangle((x0, y, x1, y + bh), radius=bh / 2, fill=PINK)
    d.rounded_rectangle((x0, y, max(split, x0 + bh), y + bh), radius=bh / 2, fill=BLUE)
    if x0 + bh < split < x1 - bh:
        d.rectangle((split - bh / 2, y, split, y + bh), fill=BLUE)
    fa, fb = f"{sa_} {score_a:.0f}%", f"{sb_} {100 - score_a:.0f}%"
    ffa = _fit(d, fa, max(split - x0 - 50, 110), 34, 20)
    ffb = _fit(d, fb, max(x1 - split - 50, 110), 34, 20)
    d.text((x0 + 30, y + bh / 2 - ffa.size * 0.62), fa, font=ffa, fill=WHITE)
    d.text((x1 - 30 - d.textlength(fb, font=ffb), y + bh / 2 - ffb.size * 0.62), fb, font=ffb, fill=WHITE)

    # 유형 두 개 (좌우 카드)
    y += bh + 50
    for i, (who, tp, col, soft) in enumerate(((sa_, type_a, BLUE, BLUE_SOFT), (sb_, type_b, PINK, PINK_SOFT))):
        bx0 = 110 + i * 440
        d.rounded_rectangle((bx0, y, bx0 + 420, y + 400), radius=34, fill=soft)
        bcx = bx0 + 210
        _ct(d, bcx, y + 30, who, _fit(d, who, 360, 32), col)
        _ct(d, bcx, y + 82, _clean(tp[0]), _fit(d, _clean(tp[0]), 370, 46), INK)
        ly = y + 160
        for line in _wrap(d, _clean(tp[1]), _f(28), 350)[:3]:
            _ct(d, bcx, ly, line, _f(28), (110, 90, 100))
            ly += 40
        st = stats[a] if i == 0 else stats[b]
        meta = f"선톡 {st['선톡 횟수']} · 답장 {_rep(st)}"
        d.line((bx0 + 60, y + 300, bx0 + 360, y + 300), fill=WHITE, width=3)
        _ct(d, bcx, y + 325, meta, _fit(d, meta, 370, 30), col)

    # 푸터
    _ct(d, cx, 1830, "재미로 보는 분석  ·  카톡 썸 분석기", _f(30), WHITE)
    return _png(img)


# ─────────────── 단톡방 카드 ───────────────
def make_group_card(room, n_members, n_msgs, period, awards, pairs):
    """awards=[(emoji, 상, 이름, 설명)], pairs=[(a, b, 케미, 답장수)]"""
    if FONT_PATH is None:
        return None
    img = _background((132, 108, 255), (255, 128, 170))
    d = ImageDraw.Draw(img)
    cx = W / 2

    _pill(d, cx, 92, "KAKAOTALK  GROUP  REPORT", _f(26), WHITE, (160, 140, 255), 26, 12)
    title = _clean(room) or "우리 단톡방"
    _ct(d, cx, 166, title, _fit(d, title, 900, 72), WHITE)
    _ct(d, cx, 272, f"{n_members}명  ·  메시지 {n_msgs:,}개  ·  {period}", _f(30), (245, 240, 255))

    _panel(img, (60, 340, 1020, 1790))
    d = ImageDraw.Draw(img)

    # 썸 의심 커플 1위 (히어로)
    y = 390
    y = _pill(d, cx, y, "썸 의심 커플 1위", _f(32), PINK, PINK_SOFT, 30, 14)
    if pairs:
        a, b, chem, n = pairs[0]
        couple = f"{_short(a)}  ♥  {_short(b)}"
        _ct(d, cx, y + 24, couple, _fit(d, couple, 860, 84), INK)
        _ring(img, cx, y + 270, 115, 22, min(chem, 100), PINK)
        d = ImageDraw.Draw(img)
        _ct(d, cx, y + 218, f"{chem:.0f}", _f(72), INK)
        _ct(d, cx, y + 305, "케미 지수", _f(26), MUTED)
        _ct(d, cx, y + 412, f"서로에게 {int(n)}번이나 10분 안에 답장했어요", _f(32), MUTED)
        y += 490
    # 2·3위
    for i, (a, b, chem, n) in enumerate(pairs[1:3]):
        bx0 = 110 + i * 440
        d.rounded_rectangle((bx0, y, bx0 + 420, y + 130), radius=30, fill=(248, 244, 255))
        _ct(d, bx0 + 210, y + 22, f"{i + 2}위  ·  케미 {chem:.0f}", _f(26), MUTED)
        c = f"{_short(a)} ♥ {_short(b)}"
        _ct(d, bx0 + 210, y + 64, c, _fit(d, c, 380, 38), INK)
    y += 200

    # 어워즈 (2열 그리드)
    _ct(d, cx, y, "단톡방 어워즈", _f(34), (132, 108, 255))
    y += 76
    tiles = awards[:6]
    for i, (_, name, who, _) in enumerate(tiles):
        col, row = i % 2, i // 2
        bx0, by0 = 110 + col * 440, y + row * 160
        if i == len(tiles) - 1 and len(tiles) % 2 == 1:
            bx0 = 330
        d.rounded_rectangle((bx0, by0, bx0 + 420, by0 + 130), radius=30, fill=(248, 244, 255))
        _ct(d, bx0 + 210, by0 + 20, _clean(name), _fit(d, _clean(name), 380, 28), MUTED)
        w = _short(who)
        _ct(d, bx0 + 210, by0 + 62, w, _fit(d, w, 380, 44), INK)

    _ct(d, cx, 1830, "재미로 보는 분석  ·  카톡 썸 분석기", _f(30), WHITE)
    return _png(img)


# ─────────────── 친구 1:1 카드 ───────────────
MINT, MINT_SOFT, SUN, SUN_SOFT = (22, 170, 140), (226, 248, 241), (240, 160, 20), (255, 245, 214)


def make_friend_card(a, b, title, desc, temp, consistency, score_a, stats, type_a, type_b):
    if FONT_PATH is None:
        return None
    img = _background((40, 196, 160), (255, 205, 90))
    d = ImageDraw.Draw(img)
    sa_, sb_ = _short(a), _short(b)
    cx = W / 2
    _pill(d, cx, 92, "KAKAOTALK  FRIEND  REPORT", _f(26), WHITE, (90, 210, 180), 26, 12)
    head = f"{sa_}  &  {sb_}"
    _ct(d, cx, 170, head, _fit(d, head, 900, 76), WHITE)
    _panel(img, (60, 300, 1020, 1790))
    d = ImageDraw.Draw(img)

    y = _pill(d, cx, 350, "우정 판정", _f(32), MINT, MINT_SOFT, 30, 14)
    _ct(d, cx, y + 22, _clean(title), _fit(d, _clean(title), 860, 92), INK)
    desc = _clean(desc).replace(_clean(a), sa_).replace(_clean(b), sb_)
    yy = y + 150
    for line in _wrap(d, desc, _f(36), 820)[:2]:
        _ct(d, cx, yy, line, _f(36), MUTED)
        yy += 50

    gy = 860
    for gx, pct, big, cap, col in ((310, temp, f"{temp:.0f}°", "우정 온도", MINT),
                                   (770, consistency * 100, f"{consistency * 100:.0f}%", "꾸준함", SUN)):
        _ring(img, gx, gy, 150, 26, pct, col, track=(236, 246, 242))
        d = ImageDraw.Draw(img)
        _ct(d, gx, gy - 58, big, _f(84), INK)
        _ct(d, gx, gy + 44, cap, _f(30), MUTED)

    y = gy + 220
    _ct(d, cx, y, "누가 더 챙길까?", _f(30), MUTED)
    y += 54
    x0, x1, bh = 120, 960, 74
    split = x0 + (x1 - x0) * score_a / 100
    d.rounded_rectangle((x0, y, x1, y + bh), radius=bh / 2, fill=SUN)
    d.rounded_rectangle((x0, y, max(split, x0 + bh), y + bh), radius=bh / 2, fill=MINT)
    if x0 + bh < split < x1 - bh:
        d.rectangle((split - bh / 2, y, split, y + bh), fill=MINT)
    fa, fb = f"{sa_} {score_a:.0f}%", f"{sb_} {100 - score_a:.0f}%"
    ffa = _fit(d, fa, max(split - x0 - 50, 110), 34, 20)
    ffb = _fit(d, fb, max(x1 - split - 50, 110), 34, 20)
    d.text((x0 + 30, y + bh / 2 - ffa.size * 0.62), fa, font=ffa, fill=WHITE)
    d.text((x1 - 30 - d.textlength(fb, font=ffb), y + bh / 2 - ffb.size * 0.62), fb, font=ffb, fill=WHITE)

    y += bh + 50
    for i, (who, tp, col, soft, key) in enumerate(((sa_, type_a, MINT, MINT_SOFT, a), (sb_, type_b, SUN, SUN_SOFT, b))):
        bx0 = 110 + i * 440
        d.rounded_rectangle((bx0, y, bx0 + 420, y + 380), radius=34, fill=soft)
        bcx = bx0 + 210
        _ct(d, bcx, y + 30, who, _fit(d, who, 360, 32), col)
        _ct(d, bcx, y + 82, _clean(tp[0]), _fit(d, _clean(tp[0]), 370, 50), INK)
        ly = y + 165
        for line in _wrap(d, _clean(tp[1]), _f(28), 350)[:3]:
            _ct(d, bcx, ly, line, _f(28), (100, 100, 100))
            ly += 40
        st = stats[key]
        meta = f"선톡 {st['선톡 횟수']} · 약속 제안 {st['약속 제안']}"
        _ct(d, bcx, y + 310, meta, _fit(d, meta, 370, 30), col)
    _ct(d, cx, 1830, "재미로 보는 분석  ·  카톡 관계 분석기", _f(30), WHITE)
    return _png(img)


def make_friend_group_card(room, n_members, n_msgs, period, pairs, roles, survival, survival_label):
    """pairs=[(a,b,케미,답장수)], roles=[(emoji, 역할, 이름, 설명)]"""
    if FONT_PATH is None:
        return None
    img = _background((40, 196, 160), (255, 205, 90))
    d = ImageDraw.Draw(img)
    cx = W / 2
    _pill(d, cx, 92, "KAKAOTALK  SQUAD  REPORT", _f(26), WHITE, (90, 210, 180), 26, 12)
    title = _clean(room) or "우리 단톡방"
    _ct(d, cx, 166, title, _fit(d, title, 900, 72), WHITE)
    _ct(d, cx, 272, f"{n_members}명  ·  메시지 {n_msgs:,}개  ·  {period}", _f(30), WHITE)
    _panel(img, (60, 340, 1020, 1790))
    d = ImageDraw.Draw(img)

    # 생존율 링 + 베프 짝꿍
    _ring(img, 260, 560, 130, 24, survival, MINT, track=(236, 246, 242))
    d = ImageDraw.Draw(img)
    _ct(d, 260, 505, f"{survival:.0f}%", _f(70), INK)
    _ct(d, 260, 590, "단톡 생존율", _f(26), MUTED)
    _ct(d, 260, 712, _clean(survival_label), _fit(d, _clean(survival_label), 360, 28), MINT)
    _ct(d, 720, 410, "베프 짝꿍 1위", _f(30), MUTED)
    if pairs:
        a, b, chem, n = pairs[0]
        c = f"{_short(a)} & {_short(b)}"
        _ct(d, 720, 460, c, _fit(d, c, 470, 60), INK)
        _ct(d, 720, 550, f"케미 {chem:.0f} · 서로 답장 {int(n)}회", _f(30), MINT)
        yy = 620
        for i, (a, b, chem, n) in enumerate(pairs[1:3]):
            c = f"{i + 2}위  {_short(a)} & {_short(b)}"
            _ct(d, 720, yy, c, _fit(d, c, 470, 34), (110, 110, 110))
            yy += 54

    y = 800
    _ct(d, cx, y, "우리 단톡방 역할", _f(34), MINT)
    y += 76
    tiles = roles[:6]
    for i, (_, name, who, desc) in enumerate(tiles):
        col, row = i % 2, i // 2
        bx0, by0 = 110 + col * 440, y + row * 225
        if i == len(tiles) - 1 and len(tiles) % 2 == 1:
            bx0 = 330
        d.rounded_rectangle((bx0, by0, bx0 + 420, by0 + 200), radius=30, fill=MINT_SOFT if i % 3 != 1 else SUN_SOFT)
        _ct(d, bx0 + 210, by0 + 24, _clean(name), _fit(d, _clean(name), 380, 30), MINT)
        w = _short(who)
        _ct(d, bx0 + 210, by0 + 68, w, _fit(d, w, 380, 50), INK)
        _ct(d, bx0 + 210, by0 + 140, _clean(desc), _fit(d, _clean(desc), 370, 26), MUTED)
    _ct(d, cx, 1830, "재미로 보는 분석  ·  카톡 관계 분석기", _f(30), WHITE)
    return _png(img)


# ─────────────── 팀플 카드 ───────────────
NAVY, SKY, SKY_SOFT, RED = (40, 60, 130), (60, 120, 255), (232, 240, 255), (240, 70, 80)


def make_team_card(room, n_members, n_msgs, period, ttype, rows, suspect):
    """ttype=(emoji, 유형, 설명), rows=[(이름, 역할, 기여도, 무임승차지수)], suspect=(이름, 지수)"""
    if FONT_PATH is None:
        return None
    img = _background((58, 96, 255), (120, 220, 255))
    d = ImageDraw.Draw(img)
    cx = W / 2
    _pill(d, cx, 92, "KAKAOTALK  TEAM  REPORT", _f(26), WHITE, (100, 140, 255), 26, 12)
    title = _clean(room) or "우리 팀플방"
    _ct(d, cx, 166, title, _fit(d, title, 900, 72), WHITE)
    _ct(d, cx, 272, f"{n_members}명  ·  메시지 {n_msgs:,}개  ·  {period}", _f(30), WHITE)
    _panel(img, (60, 340, 1020, 1790))
    d = ImageDraw.Draw(img)

    y = _pill(d, cx, 390, "팀 유형", _f(30), SKY, SKY_SOFT, 30, 12)
    _ct(d, cx, y + 18, _clean(ttype[1]), _fit(d, _clean(ttype[1]), 860, 80), INK)
    for line in _wrap(d, _clean(ttype[2]), _f(32), 820)[:2]:
        _ct(d, cx, y + 128, line, _f(32), MUTED)
        y += 44

    # 기여도 막대
    y = 700
    _ct(d, cx, y, "기여도 랭킹", _f(32), SKY)
    y += 66
    for i, (name, role, contrib, fr) in enumerate(rows[:6]):
        nm = _short(name)
        d.text((120, y + 4), f"{i + 1}", font=_f(36), fill=SKY if i == 0 else MUTED)
        d.text((175, y), nm, font=_fit(d, nm, 170, 38), fill=INK)
        rl = _clean(role)
        d.text((175, y + 48), rl, font=_fit(d, rl, 190, 24), fill=MUTED)
        bx0, bx1 = 380, 860
        d.rounded_rectangle((bx0, y + 14, bx1, y + 58), radius=22, fill=(238, 242, 250))
        col = SKY if fr < 50 else (RED if fr >= 70 else (250, 170, 60))
        d.rounded_rectangle((bx0, y + 14, bx0 + max((bx1 - bx0) * contrib / 100, 44), y + 58), radius=22, fill=col)
        d.text((878, y + 10), f"{contrib:.0f}", font=_f(38), fill=INK)
        y += 128

    # 무임승차 의심
    y = max(y + 20, 1480)
    name, val = suspect
    box_col = (255, 236, 236) if val >= 70 else ((255, 244, 225) if val >= 50 else SKY_SOFT)
    d.rounded_rectangle((110, y, 970, y + 230), radius=36, fill=box_col)
    if val >= 50:
        _ct(d, cx, y + 30, "무임승차 탐지기", _f(30), RED if val >= 70 else (220, 130, 30))
        t = f"{_short(name)}  {val:.0f}%"
        _ct(d, cx, y + 80, t, _fit(d, t, 800, 64), INK)
        _ct(d, cx, y + 168, "의심 지수 (재미로만 봐주세요)", _f(26), MUTED)
    else:
        _ct(d, cx, y + 40, "무임승차 탐지기", _f(30), SKY)
        _ct(d, cx, y + 95, "무임승차 없음!", _f(64), INK)
    _ct(d, cx, 1830, "재미로 보는 분석  ·  카톡 관계 분석기", _f(30), WHITE)
    return _png(img)
