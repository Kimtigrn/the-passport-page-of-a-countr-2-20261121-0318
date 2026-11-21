#!/usr/bin/env python3
"""The Passport Page of a Country That Isn't There.

Draws one open passport spread for the invented Republic of Valdris --
a North Atlantic island republic whose capital is Port Sarn -- and writes
it to /output/entry.png (1024x720, PNG, stdlib only, deterministic).

Left page: the data page. Portrait of the holder, Elena Maris Voss,
personal data, and a machine-readable zone with correct ICAO check
digits. Right page: the travel history -- entry/exit stamps from the
three neighbouring states (Ostara, Dravnik, Kalmere), a Kalmere visa,
and the conditions of issue, including the telling detail that the
passport is not valid for travel to the Northern Fisheries without a
permit.

Every date agrees: the passport was issued 02 JUN 2025 and every stamp
falls after that date. The portrait, the place-name Port Sarn and the
lighthouse emblem all belong to the same island-port country.

Run:  python3 main.py            (writes /output/entry.png)
"""
import os
import struct
import zlib

# ---------------------------------------------------------------- canvas
W, H = 1024, 720          # logical size; rendered at SSx and downsampled
SS = 2                     # supersampling factor (smooth edges)
PW, PH = W * SS, H * SS

PAPER = (245, 240, 225)
PAPER2 = (238, 231, 210)
NAVY = (27, 42, 74)
NAVY2 = (36, 54, 94)
GOLD = (176, 138, 46)
GOLD_LT = (201, 164, 80)
INK = (32, 36, 42)
GREY = (90, 95, 106)
FAINT = (214, 206, 184)
LINE = (120, 110, 88)
STAMP_BLUE = (43, 76, 155)
STAMP_RED = (166, 58, 46)
STAMP_GREEN = (46, 107, 79)
STAMP_PURPLE = (107, 63, 160)
SKIN = (232, 195, 154)
SKIN_DK = (214, 172, 128)
HAIR = (74, 52, 38)
JACKET = (38, 56, 92)
PHOTO_BG = (198, 209, 217)
WHITE = (252, 250, 244)


class Canvas:
    def __init__(self):
        self.buf = bytearray(PW * PH * 3)
        self.fill(PAPER)

    def fill(self, color):
        r, g, b = color
        row = bytes((r, g, b)) * PW
        self.buf[:] = row * PH

    def _idx(self, x, y):
        return (y * PW + x) * 3

    def px(self, x, y, color):
        if 0 <= x < PW and 0 <= y < PH:
            i = self._idx(x, y)
            self.buf[i:i + 3] = bytes(color)

    def fill_rect(self, x, y, w, h, color):
        x0, y0 = max(0, x * SS), max(0, y * SS)
        x1, y1 = min(PW, (x + w) * SS), min(PH, (y + h) * SS)
        if x1 <= x0 or y1 <= y0:
            return
        r, g, b = color
        seg = bytes((r, g, b)) * (x1 - x0)
        for yy in range(y0, y1):
            i = (yy * PW + x0) * 3
            self.buf[i:i + len(seg)] = seg

    def rect(self, x, y, w, h, color, t=1):
        self.fill_rect(x, y, w, t, color)
        self.fill_rect(x, y + h - t, w, t, color)
        self.fill_rect(x, y, t, h, color)
        self.fill_rect(x + w - t, y, t, h, color)

    def hline(self, x0, x1, y, color, t=1):
        self.fill_rect(x0, y, x1 - x0, t, color)

    def vline(self, x, y0, y1, color, t=1):
        self.fill_rect(x, y0, t, y1 - y0, color)

    def line(self, x0, y0, x1, y1, color):
        x0, y0, x1, y1 = x0 * SS, y0 * SS, x1 * SS, y1 * SS
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        x, y = x0, y0
        while True:
            self.px(x, y, color)
            if x == x1 and y == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy

    def circle(self, cx, cy, r, color, fill=False):
        cx, cy, r = cx * SS, cy * SS, r * SS
        if fill:
            x, y, d = 0, r, 1 - r
            while x <= y:
                self._span_ss(cx, cy, x, y, color)
                if d < 0:
                    d += 2 * x + 3
                else:
                    d += 2 * (x - y) + 5
                    y -= 1
                x += 1
        else:
            x, y, d = 0, r, 1 - r
            while x <= y:
                for sx, sy in ((x, y), (y, x), (-x, y), (-y, x),
                               (x, -y), (y, -x), (-x, -y), (-y, -x)):
                    self.px(cx + sx, cy + sy, color)
                if d < 0:
                    d += 2 * x + 3
                else:
                    d += 2 * (x - y) + 5
                    y -= 1
                x += 1

    def _span_ss(self, cx, cy, x, y, color):
        # horizontal spans for a filled circle, in supersampled coords
        for yy, xx in ((cy + y, x), (cy - y, x)):
            i = (yy * PW + cx - xx) * 3
            n = 2 * xx + 1
            if 0 <= yy < PH and cx - xx >= 0 and cx + xx < PW:
                self.buf[i:i + n * 3] = bytes(color) * n

    def ellipse(self, cx, cy, rx, ry, color, fill=False):
        cx, cy, rx, ry = cx * SS, cy * SS, rx * SS, ry * SS
        if fill:
            for yy in range(cy - ry, cy + ry + 1):
                if not (0 <= yy < PH):
                    continue
                t = (yy - cy) / ry
                xw = int(rx * (1 - t * t) ** 0.5)
                i = (yy * PW + cx - xw) * 3
                n = 2 * xw + 1
                if cx - xw >= 0 and cx + xw < PW:
                    self.buf[i:i + n * 3] = bytes(color) * n
        else:
            steps = max(8, int(2 * 3.14159 * max(rx, ry)))
            import math
            for k in range(steps):
                a = 2 * math.pi * k / steps
                self.px(int(cx + rx * math.cos(a)),
                        int(cy + ry * math.sin(a)), color)

    def polygon(self, pts, color):
        # scanline fill; pts in logical coords
        pts = [(x * SS, y * SS) for x, y in pts]
        ys = [p[1] for p in pts]
        for yy in range(max(0, min(ys)), min(PH, max(ys) + 1)):
            xs = []
            n = len(pts)
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 <= yy < y1) or (y1 <= yy < y0):
                    xs.append(x0 + (yy - y0) * (x1 - x0) / (y1 - y0))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                x0, x1 = int(xs[k]), int(xs[k + 1])
                if x1 <= x0:
                    continue
                i = (yy * PW + max(0, x0)) * 3
                m = min(PW, x1) - max(0, x0)
                if m > 0:
                    self.buf[i:i + m * 3] = bytes(color) * m

    def downsample_png(self):
        out = bytearray()
        for oy in range(H):
            row = bytearray(b"\x00")
            y0 = oy * SS
            for ox in range(W):
                x0 = ox * SS
                r = g = b = 0
                for dy in range(SS):
                    base = ((y0 + dy) * PW + x0) * 3
                    for dx in range(SS):
                        i = base + dx * 3
                        r += self.buf[i]
                        g += self.buf[i + 1]
                        b += self.buf[i + 2]
                n = SS * SS
                row += bytes((r // n, g // n, b // n))
            out += row
        raw = bytes(out)
        comp = zlib.compress(raw, 6)
        png = bytearray(b"\x89PNG\r\n\x1a\n")
        ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
        png += _chunk(b"IHDR", ihdr)
        png += _chunk(b"IDAT", comp)
        png += _chunk(b"IEND", b"")
        return bytes(png)


def _chunk(tag, data):
    import binascii
    out = struct.pack(">I", len(data)) + tag + data
    out += struct.pack(">I", binascii.crc32(tag + data) & 0xFFFFFFFF)
    return out


# ------------------------------------------------------------------- font
# 5x7 bitmap font, uppercase + digits + punctuation. '#' = ink.
FONT = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01111", "10000", "10000", "10111", "10001", "10001", "01110"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "J": ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    "6": ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "00100", "00100", "00100"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00001", "01110"),
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    ",": ("00000", "00000", "00000", "00000", "01100", "01100", "01000"),
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    "/": ("00001", "00001", "00010", "00010", "00100", "01000", "10000"),
    "(": ("00010", "00100", "01000", "01000", "01000", "00100", "00010"),
    ")": ("01000", "00100", "00010", "00010", "00010", "00100", "01000"),
    "'": ("00100", "00100", "01000", "00000", "00000", "00000", "00000"),
    ":": ("00000", "01100", "01100", "00000", "01100", "01100", "00000"),
    "<": ("00010", "00100", "01000", "10000", "01000", "00100", "00010"),
    ">": ("01000", "00100", "00010", "00001", "00010", "00100", "01000"),
    "&": ("01100", "10010", "10010", "01000", "10101", "10010", "01101"),
    "+": ("00000", "00100", "00100", "11111", "00100", "00100", "00000"),
    '"': ("01010", "01010", "00000", "00000", "00000", "00000", "00000"),
    "!": ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    "?": ("01110", "10001", "00001", "00010", "00100", "00000", "00100"),
    "=": ("00000", "00000", "11111", "00000", "11111", "00000", "00000"),
}


def text_width(s, scale, adv=6):
    return len(s) * adv * scale - scale


def draw_text(cv, s, x, y, scale, color, adv=6):
    cx = x
    for ch in s.upper():
        g = FONT.get(ch, FONT[" "])
        for row in range(7):
            bits = g[row]
            for col in range(5):
                if bits[col] == "1":
                    cv.fill_rect(cx + col * scale, y + row * scale,
                                 scale, scale, color)
        cx += adv * scale
    return cx


def draw_text_c(cv, s, cx, y, scale, color, adv=6):
    w = text_width(s, scale, adv)
    draw_text(cv, s, cx - w // 2, y, scale, color, adv)
    return w


# --------------------------------------------------------------------- mrz
def _mrz_value(ch):
    if ch.isdigit():
        return int(ch)
    if ch == "<":
        return 0
    return ord(ch) - 55  # A=10 .. Z=35


def mrz_check(s):
    total = 0
    for i, ch in enumerate(s):
        total += _mrz_value(ch) * (7, 3, 1)[i % 3]
    return str(total % 10)


def mrz_lines():
    line1 = "P<VLDVOSS<<ELENA<MARIS"
    line1 = line1 + "<" * (44 - len(line1))
    doc = "VLD847291"
    dob = "880314"
    exp = "350602"
    pers = "<" * 14
    line2 = (doc + mrz_check(doc) + "VLD" + dob + mrz_check(dob) + "F"
             + exp + mrz_check(exp) + pers + mrz_check(pers))
    comp = (doc + mrz_check(doc) + "VLD" + dob + mrz_check(dob)
            + exp + mrz_check(exp) + pers + mrz_check(pers))
    line2 += mrz_check(comp)
    assert len(line1) == 44 and len(line2) == 44, (line1, line2)
    return line1, line2


# ------------------------------------------------------------------ emblem
def draw_emblem(cv, cx, cy, r, color, bg=None):
    """Lighthouse over waves inside a ring: the arms of Valdris."""
    if bg is not None:
        cv.circle(cx, cy, r, bg, fill=True)
    cv.circle(cx, cy, r, color)
    cv.circle(cx, cy, r - 3, color)
    # sea: three wave lines
    for i, wy in enumerate((cy + r // 2 - 2, cy + r // 2 + 3, cy + r // 2 + 8)):
        cv.hline(cx - r + 8 + i * 2, cx + r - 8 - i * 2, wy, color, 2)
    # lighthouse: tapered tower + lamp room + light rays
    cv.polygon([(cx - 6, cy + r // 2 - 4), (cx + 6, cy + r // 2 - 4),
                (cx + 4, cy - r // 2 + 6), (cx - 4, cy - r // 2 + 6)], color)
    cv.fill_rect(cx - 6, cy - r // 2 + 1, 12, 5, color)
    cv.fill_rect(cx - 2, cy - r // 2 - 3, 4, 3, color)
    cv.line(cx - 8, cy - r // 2 + 2, cx - r + 4, cy - r // 2 - 2, color)
    cv.line(cx + 8, cy - r // 2 + 2, cx + r - 4, cy - r // 2 - 2, color)


# ---------------------------------------------------------------- portrait
def draw_portrait(cv, x, y, w, h):
    """Flat-style passport photo of Elena Maris Voss, 36, of Port Sarn."""
    cv.fill_rect(x, y, w, h, PHOTO_BG)
    # backdrop: pale vertical bands
    cv.fill_rect(x + 8, y, 6, h, (210, 219, 226))
    cv.fill_rect(x + w - 26, y, 6, h, (210, 219, 226))
    cx = x + w // 2
    # shoulders / jacket
    cv.polygon([(cx - 52, y + h), (cx - 46, y + 128), (cx - 18, y + 116),
                (cx + 18, y + 116), (cx + 46, y + 128), (cx + 52, y + h)],
               JACKET)
    # shirt collar
    cv.polygon([(cx - 14, y + 118), (cx, y + 138), (cx + 14, y + 118),
                (cx + 8, y + 112), (cx - 8, y + 112)], WHITE)
    # neck
    cv.fill_rect(cx - 11, y + 96, 22, 24, SKIN_DK)
    # face
    cv.ellipse(cx, y + 66, 33, 42, SKIN, fill=True)
    # jaw shading
    cv.ellipse(cx, y + 88, 26, 18, SKIN_DK, fill=True)
    cv.ellipse(cx, y + 82, 24, 16, SKIN, fill=True)
    # hair: bob cut framing the face, parted left
    cv.polygon([(cx - 36, y + 96), (cx - 38, y + 46), (cx - 28, y + 22),
                (cx - 6, y + 16), (cx + 18, y + 18), (cx + 34, y + 34),
                (cx + 38, y + 58), (cx + 36, y + 96), (cx + 28, y + 96),
                (cx + 30, y + 52), (cx + 22, y + 32), (cx - 2, y + 28),
                (cx - 24, y + 34), (cx - 30, y + 54), (cx - 28, y + 96)],
               HAIR)
    # brows
    cv.fill_rect(cx - 22, y + 56, 14, 3, HAIR)
    cv.fill_rect(cx + 8, y + 56, 14, 3, HAIR)
    # eyes
    cv.ellipse(cx - 15, y + 65, 5, 3, WHITE, fill=True)
    cv.ellipse(cx + 15, y + 65, 5, 3, WHITE, fill=True)
    cv.ellipse(cx - 15, y + 65, 2, 3, INK, fill=True)
    cv.ellipse(cx + 15, y + 65, 2, 3, INK, fill=True)
    # nose
    cv.line(cx, y + 66, cx - 2, y + 80, SKIN_DK)
    cv.line(cx - 2, y + 80, cx + 3, y + 82, SKIN_DK)
    # mouth
    cv.fill_rect(cx - 9, y + 92, 18, 3, (176, 110, 96))
    # earring
    cv.circle(cx - 33, y + 92, 2, GOLD, fill=True)
    cv.circle(cx + 33, y + 92, 2, GOLD, fill=True)
    # photo frame
    cv.rect(x, y, w, h, NAVY, 2)


# ------------------------------------------------------------------ stamps
def rect_stamp(cv, x, y, w, h, color, lines, scale=2, tilt=0):
    """Rectangular border-control stamp; lines = list of (text, scale)."""
    cv.rect(x, y, w, h, color, 2)
    cv.rect(x + 4, y + 4, w - 8, h - 8, color, 1)
    yy = y + 10
    for text, sc in lines:
        draw_text_c(cv, text, x + w // 2, yy, sc, color)
        yy += 7 * sc + 5


def circle_stamp(cv, cx, cy, r, color, ring_text, center_lines):
    cv.circle(cx, cy, r, color)
    cv.circle(cx, cy, r - 5, color)
    # ring text approximated by a straight line across the top arc area
    draw_text_c(cv, ring_text, cx, cy - r + 9, 2, color)
    yy = cy - 12
    for text, sc in center_lines:
        draw_text_c(cv, text, cx, yy, sc, color)
        yy += 7 * sc + 4
    draw_text_c(cv, ring_text, cx, cy + r - 20, 2, color)


def guilloche(cv):
    """Faint concentric arcs rising from the spine's foot, like a watermark."""
    import math
    cx, cy = 512, 720
    for k in range(9):
        r = 150 + k * 26
        steps = 220
        for i in range(steps):
            a = math.pi * (1.0 + i / steps * 0.5)
            cv.px(int((cx + r * math.cos(a)) * SS),
                  int((cy + r * math.sin(a)) * SS), FAINT)


# -------------------------------------------------------------------- pages
def field(cv, x, y, label, value, vscale=3):
    draw_text(cv, label, x, y, 2, GREY)
    draw_text(cv, value, x, y + 16, vscale, INK)


def draw_left_page(cv):
    draw_text(cv, "DATA PAGE", 36, 102, 2, GREY)
    draw_text(cv, "PAGE 8", 440, 102, 2, GREY)
    draw_portrait(cv, 36, 122, 150, 188)
    field(cv, 204, 122, "SURNAME", "VOSS")
    field(cv, 204, 162, "GIVEN NAMES", "ELENA MARIS")
    field(cv, 204, 202, "NATIONALITY", "VALDRISIAN")
    field(cv, 204, 242, "DATE OF BIRTH", "14 MAR 1988")
    field(cv, 204, 282, "PLACE OF BIRTH", "PORT SARN")
    field(cv, 36, 330, "SEX", "F")
    field(cv, 260, 330, "DOCUMENT NO.", "VLD 847 291")
    field(cv, 36, 380, "DATE OF ISSUE", "02 JUN 2025")
    field(cv, 260, 380, "DATE OF EXPIRY", "02 JUN 2035")
    field(cv, 36, 430, "AUTHORITY", "PASSPORT OFFICE, PORT SARN", vscale=2)
    # holder's signature: a looping flourish above a rule
    draw_text(cv, "SIGNATURE OF HOLDER", 36, 482, 2, GREY)
    cv.line(44, 516, 70, 502, INK)
    cv.line(70, 502, 92, 518, INK)
    cv.line(92, 518, 118, 504, INK)
    cv.line(118, 504, 140, 516, INK)
    cv.line(140, 516, 168, 503, INK)
    cv.line(168, 503, 196, 515, INK)
    cv.line(196, 515, 226, 506, INK)
    cv.line(226, 506, 252, 514, INK)
    cv.hline(36, 260, 524, NAVY, 1)
    # machine-readable zone
    cv.fill_rect(28, 588, 456, 58, WHITE)
    cv.rect(28, 588, 456, 58, NAVY, 1)
    l1, l2 = mrz_lines()
    draw_text(cv, l1, 36, 598, 2, INK, adv=5)
    draw_text(cv, l2, 36, 622, 2, INK, adv=5)
    draw_text(cv, "8", 40, 686, 2, GREY)


def draw_right_page(cv):
    draw_text_c(cv, "VISAS - STAMPS", 761, 102, 3, NAVY)
    rect_stamp(cv, 540, 140, 200, 110, STAMP_BLUE,
               [("OSTARA", 3), ("ENTRY", 3), ("18 JUL 2025", 2),
                ("PORT OF VELKA", 2)])
    rect_stamp(cv, 772, 140, 200, 110, STAMP_RED,
               [("OSTARA", 3), ("EXIT", 3), ("02 AUG 2025", 2),
                ("PORT OF VELKA", 2)])
    rect_stamp(cv, 532, 276, 224, 108, STAMP_GREEN,
               [("DRAVNIK", 3), ("ENTRY 11 SEP 2025", 2),
                ("EXIT 25 SEP 2025", 2)])
    circle_stamp(cv, 872, 335, 62, STAMP_PURPLE, "KALMERE",
                 [("ENTRY", 3), ("03 NOV 2025", 2)])
    # Kalmere visa
    cv.rect(540, 430, 432, 115, NAVY, 2)
    draw_text(cv, "VISA - KALMERE", 556, 444, 3, NAVY)
    draw_text(cv, "SINGLE ENTRY, 90 DAYS", 556, 474, 2, INK)
    draw_text(cv, "NOT VALID FOR PAID WORK", 556, 496, 2, INK)
    draw_text(cv, "ISSUED AT THE BORDER, PORT SARN", 556, 518, 2, INK)
    cv.rect(880, 442, 76, 40, STAMP_PURPLE, 2)
    draw_text_c(cv, "PAID", 918, 448, 2, STAMP_PURPLE)
    draw_text_c(cv, "12 KRD", 918, 464, 2, STAMP_PURPLE)
    # conditions of issue -- the telling detail is condition 2
    cv.rect(540, 560, 432, 134, NAVY, 1)
    draw_text(cv, "CONDITIONS OF ISSUE", 556, 572, 2, NAVY)
    for i, ln in enumerate((
            "1. PROPERTY OF THE REPUBLIC OF",
            "VALDRIS. LOSS MUST BE REPORTED",
            "AT ONCE TO THE NEAREST OFFICE.",
            "2. NOT VALID FOR TRAVEL TO THE",
            "NORTHERN FISHERIES WITHOUT A",
            "PERMIT. - PORT SARN")):
        draw_text(cv, ln, 556, 592 + i * 17, 2, INK)
    draw_text(cv, "9", 976, 686, 2, GREY)


def build():
    cv = Canvas()
    guilloche(cv)
    cv.rect(8, 8, 1008, 704, NAVY, 3)
    cv.rect(14, 14, 996, 692, NAVY, 1)
    cv.vline(511, 14, 706, NAVY, 2)
    draw_emblem(cv, 58, 50, 26, GOLD, bg=NAVY)
    draw_text_c(cv, "REPUBLIC OF VALDRIS", 512, 28, 4, NAVY)
    draw_text_c(cv, "REPUBLIKA VALDRIS - PASSPORT", 512, 58, 2, GOLD)
    cv.hline(24, 1000, 88, NAVY, 2)
    draw_left_page(cv)
    draw_right_page(cv)
    return cv.downsample_png()


def main():
    data = build()
    outdir = os.environ.get("OUTPUT_DIR") or "/output"
    try:
        os.makedirs(outdir, exist_ok=True)
    except OSError:
        outdir = "output"
        os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "entry.png")
    with open(path, "wb") as f:
        f.write(data)
    l1, l2 = mrz_lines()
    print("wrote", path, len(data), "bytes")
    print("MRZ:", l1)
    print("MRZ:", l2)


if __name__ == "__main__":
    main()
