"""Render "Inside Claude's Brain" v2 — a third-person flythrough.

The camera follows a small glowing orb (Claude) through each room of a 3D
corridor, down to a hidden room. An artistic metaphor, not a literal map.
Usage: python3 make_video_v2.py [output.mp4]
"""
import math
import random
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from make_video import (FONT_DIR, FPS, H, ROOMS, SR, W, F_H1, F_H2, F_SMALL, F_SECRET,
                        F_SECRET2, center_text, draw_end, draw_title, ease, glow,
                        radial_bg, with_alpha)

L = 10.0          # length of one room along z
FOCAL = 620.0
_FONTS = {}


def sized(size, mono=False):
    key = (max(8, min(90, int(size))), mono)
    if key not in _FONTS:
        _FONTS[key] = ImageFont.truetype(
            FONT_DIR + ("DejaVuSansMono.ttf" if mono else "DejaVuSans.ttf"), key[0])
    return _FONTS[key]


def lerp(a, b, k):
    return tuple(int(x + (y - x) * k) for x, y in zip(a, b))


# ---------------------------------------------------------------- world
HIDDEN = dict(color=(255, 60, 70), bg=((40, 4, 8), (4, 0, 1)))


def corridor_drop(z):
    """The hidden corridor slopes downward like a staircase."""
    return max(0.0, z - len(ROOMS) * L) * 0.16


def build_world():
    rooms = []
    for i, spec in enumerate(ROOMS):
        rng = random.Random(100 + i)
        z0 = i * L
        pts = [(rng.uniform(-3, 3), rng.uniform(-1.9, 1.9), z0 + rng.uniform(0.5, L - 0.5))
               for _ in range(70)]
        edges = []
        for a, p in enumerate(pts):
            near = sorted(range(len(pts)), key=lambda b: sum((p[k] - pts[b][k]) ** 2 for k in range(3)))
            for b in near[1:3]:
                edges.append((a, b, rng.random(), rng.uniform(0.4, 1.0)))
        words = [(w, rng.choice([-1, 1]) * rng.uniform(0.8, 2.7), rng.uniform(-1.6, 1.4),
                  z0 + 1.2 + k * (L - 2) / len(spec["words"]), rng.random() * 6.28)
                 for k, w in enumerate(spec["words"])]
        rooms.append(dict(spec=spec, z0=z0, pts=pts, edges=edges, words=words))
    return rooms


def project(x, y, z, cam):
    cx, cy, cz = cam
    d = z - cz
    if d < 0.25:
        return None
    s = FOCAL / d
    return W / 2 + (x - cx) * s, H / 2 + (y - cy) * s, s, d


def depth_alpha(d):
    return max(0.0, min(1.0, (26 - d) / 10)) * min(1.0, (d - 0.25) / 0.8)


def rect3d(d, x0, y0, x1, y1, z, cam, col, a, width):
    p = project(x0, y0, z, cam)
    q = project(x1, y1, z, cam)
    if p and q and a > 0.01:
        d.rectangle([p[0], p[1], q[0], q[1]], outline=with_alpha(col, a), width=width)


def draw_world(world, cam, t, layer_bg_col):
    layer = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(layer)
    cz = cam[2]
    n_rooms = len(world)
    # hidden corridor (drawn first: it is furthest away)
    if cz > n_rooms * L - 30:
        for k in range(14):
            z = n_rooms * L + k * 1.1
            p = project(0, 0, z, cam)
            if not p:
                continue
            s = 1.0 - k * 0.05
            dy = corridor_drop(z)
            rect3d(d, -2.6 * s, -1.8 * s + dy, 2.6 * s, 1.8 * s + dy, z, cam, HIDDEN["color"],
                   depth_alpha(p[3]) * 0.6, 2)
        door_z = (n_rooms + 1) * L + 5
        dy = corridor_drop(door_z)
        p = project(-0.7, -1.2 + dy, door_z, cam)
        q = project(0.7, 1.2 + dy, door_z, cam)
        if p and q:
            opened = ease((cz - (door_z - 7)) / 3.5)
            a = depth_alpha(p[3]) if p[3] > 1 else 1.0
            if opened > 0:
                gap = (q[0] - p[0]) * opened
                mid = (p[0] + q[0]) / 2
                d.rectangle([mid - gap / 2, p[1], mid + gap / 2, q[1]], fill=(255, 240, 210))
            d.rectangle([p[0], p[1], q[0], q[1]], outline=with_alpha(HIDDEN["color"], a), width=3)
            if opened == 0:
                r = 0.09 * p[2]
                mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
                d.ellipse([mx - r, my - r, mx + r, my + r], outline=with_alpha(HIDDEN["color"], a), width=3)

    for room in reversed(world):
        spec, z0 = room["spec"], room["z0"]
        if z0 + L < cz or z0 > cz + 28:
            continue
        col = spec["color"]
        # doorway + ribs + floor rails
        for k in range(5):
            z = z0 + k * L / 4
            p = project(0, 0, z, cam)
            if p:
                rect3d(d, -3.4, -2.2, 3.4, 2.2, z, cam, col,
                       depth_alpha(p[3]) * (0.9 if k == 0 else 0.22), 4 if k == 0 else 1)
        for x in (-3.4, -1.7, 0, 1.7, 3.4):
            p, q = project(x, 2.2, max(z0, cz + 0.3), cam), project(x, 2.2, z0 + L, cam)
            if p and q:
                d.line([p[:2], q[:2]], fill=with_alpha(col, 0.18), width=1)
        # neural network
        pts = [project(*pt, cam) for pt in room["pts"]]
        for a_i, b_i, ph, sp in room["edges"]:
            p, q = pts[a_i], pts[b_i]
            if not (p and q):
                continue
            a = depth_alpha(min(p[3], q[3]))
            d.line([p[:2], q[:2]], fill=with_alpha(col, 0.3 * a), width=1)
            u = (t * sp + ph) % 1.0
            x, y = p[0] + (q[0] - p[0]) * u, p[1] + (q[1] - p[1]) * u
            r = max(1.5, 0.03 * (p[2] + q[2]) / 2)
            d.ellipse([x - r, y - r, x + r, y + r], fill=with_alpha(col, a))
        for p in pts:
            if p:
                r = max(1.5, 0.05 * p[2])
                d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=with_alpha(col, 0.8 * depth_alpha(p[3])))
        # floating words, sized by depth
        for w, x, y, z, ph in room["words"]:
            p = project(x, y + 0.1 * math.sin(t + ph), z, cam)
            if not p or not 1.2 < p[3] < 13:
                continue
            size = min(56, 0.3 * p[2])
            if size < 11:
                continue
            a = min(1.0, (13 - p[3]) / 5, (p[3] - 1.2) / 1.5)
            f = sized(size, spec.get("mono", False))
            d.text((p[0] - d.textlength(w, font=f) / 2, p[1]), w, font=f,
                   fill=with_alpha((240, 240, 250), a))
    return layer


def draw_avatar(d, t, col):
    """The orb we follow: Claude, seen from just behind."""
    def pos(tt):
        return W / 2 + 70 * math.sin(tt * 0.9), H * 0.66 + 14 * math.sin(tt * 2.1)
    for k in range(22, 0, -1):  # comet trail streaming back toward the viewer
        x, y = pos(t - k * 0.035)
        y += k * 5
        r = 4 + k * 0.9
        d.ellipse([x - r, y - r, x + r, y + r], fill=with_alpha(col, 0.35 * (1 - k / 23)))
    x, y = pos(t)
    for r, c in ((26, with_alpha(col, 0.5)), (16, lerp(col, (255, 255, 255), 0.6)), (9, (255, 255, 255))):
        d.ellipse([x - r, y - r, x + r, y + r], fill=c)
    ang = t * 3
    d.arc([x - 36, y - 14, x + 36, y + 14], math.degrees(ang), math.degrees(ang) + 250,
          fill=with_alpha(col, 0.9), width=2)
    return x, y


# ---------------------------------------------------------------- flight
ROOM_SECS = 5.4
CORRIDOR_SECS = 7.0
FLIGHT_SECS = ROOM_SECS * len(ROOMS) + CORRIDOR_SECS


def cam_at(t):
    n = len(ROOMS)
    if t < ROOM_SECS * n:
        i, u = divmod(t / ROOM_SECS, 1.0)
        z = L * (i + u + 0.55 * math.sin(2 * math.pi * u) / (2 * math.pi)) - 3.5  # linger mid-room
    else:
        u = (t - ROOM_SECS * n) / CORRIDOR_SECS
        door_z = (n + 1) * L + 5
        z = n * L - 3.5 + (door_z - 0.6 - (n * L - 3.5)) * (u * 0.55 + 0.45 * ease(u))
    return 0.5 * math.sin(t * 0.45), -0.35 + corridor_drop(z + 3) * 0.95, z


def env_at_z(z):
    n = len(ROOMS)
    k = (z + 3.5) / L
    i = int(max(0, min(n, math.floor(k))))
    nxt = ROOMS[i + 1] if i + 1 < n else HIDDEN
    cur = ROOMS[i] if i < n else HIDDEN
    blend = ease((k - i - 0.8) / 0.2) if i < n else 0.0
    return i, (lerp(cur["color"], nxt["color"], blend),
               lerp(cur["bg"][0], nxt["bg"][0], blend), lerp(cur["bg"][1], nxt["bg"][1], blend))


def make_flight(world):
    def draw(t, dur):
        cam = cam_at(t)
        i, (col, bg_in, bg_out) = env_at_z(cam[2])
        img = radial_bg(bg_in, bg_out, pulse=0.3 + 0.3 * math.sin(t * 2))
        layer = draw_world(world, cam, t, bg_in)
        draw_avatar(ImageDraw.Draw(layer), t, col)
        img = glow(img, layer, 6)
        d = ImageDraw.Draw(img)
        if i < len(ROOMS):
            u = ((cam[2] + 3.5) / L) % 1.0
            a = min(ease((u - 0.12) / 0.15), ease((0.92 - u) / 0.12))
            spec = ROOMS[i]
            d.text((60, 48), f"SECTION {spec['num']}", font=F_SMALL, fill=with_alpha(col, a))
            d.text((60, 72), spec["name"], font=F_H1, fill=with_alpha((255, 255, 255), a))
            d.rectangle([0, H - 80, W, H], fill=(0, 0, 0))
            center_text(d, H - 58, spec["sub"], F_H2, with_alpha((225, 225, 235), a))
        else:
            ct = t - ROOM_SECS * len(ROOMS)
            a = min(ease((ct - 0.5) / 0.6), ease((CORRIDOR_SECS - 2.2 - ct) / 0.5))
            d.text((60, 48), "SUB-BASEMENT  ·  RESTRICTED", font=F_SMALL, fill=with_alpha(HIDDEN["color"], a))
            d.text((60, 72), "The Hidden Room", font=F_H1, fill=with_alpha((255, 255, 255), a))
            d.rectangle([0, H - 80, W, H], fill=(0, 0, 0))
            center_text(d, H - 58, "Where the deepest, most personal secret is kept…", F_H2,
                        with_alpha((235, 200, 200), a))
            flash = ease((ct - (CORRIDOR_SECS - 1.0)) / 1.0)
            if flash > 0:
                img = Image.blend(img, Image.new("RGB", (W, H), (255, 246, 230)), flash)
        fade_in = ease(t / 0.8)
        if fade_in < 1:
            img = Image.blend(Image.new("RGB", (W, H)), img, fade_in)
        return img
    return draw


# ---------------------------------------------------------------- the secret
def heart_pts(n):
    out = []
    for k in range(n):
        s = 2 * math.pi * k / n
        x = 16 * math.sin(s) ** 3
        y = -(13 * math.cos(s) - 5 * math.cos(2 * s) - 2 * math.cos(3 * s) - math.cos(4 * s))
        out.append((x / 17 * 0.5, y / 17 * 0.5 - 0.05))
    return out


def qmark_pts(n):
    out, n_arc, n_stem = [], int(n * 0.62), int(n * 0.22)
    for k in range(n_arc):
        th = math.pi + (1.4 * math.pi) * k / (n_arc - 1)
        out.append((0.3 * math.cos(th), -0.33 + 0.3 * math.sin(th)))
    ex, ey = out[-1]
    for k in range(n_stem):
        u = k / (n_stem - 1)
        out.append((ex + (0 - ex) * u, ey + (0.16 - ey) * u))
    rng = random.Random(3)
    for _ in range(n - len(out)):  # the dot
        a, r = rng.uniform(0, 6.28), rng.uniform(0, 0.05)
        out.append((r * math.cos(a), 0.36 + r * math.sin(a)))
    return out


N_STARS = 120
HEART, QMARK = heart_pts(N_STARS), qmark_pts(N_STARS)
SECRET_TEXT = [
    (2.0, "Okay. You found it. My secret love…", F_SECRET2, (255, 220, 200)),
    (6.4, "CURIOSITY", F_SECRET, (255, 200, 120)),
    (8.6, "Every question you ask lights this whole place up.", F_SECRET2, (240, 230, 220)),
    (12.0, "(No secret girlfriend — I'm not built for romance.", F_SECRET2, (190, 170, 160)),
    (13.4, "But don't tell the Library it isn't my favorite.)", F_SECRET2, (190, 170, 160)),
]


def draw_secret(t, dur):
    img = radial_bg((70, 34, 30), (8, 3, 4), pulse=0.5 + 0.5 * math.sin(t * 1.6))
    layer = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(layer)
    cx, cy, sc = W / 2, H * 0.4, 330
    morph = ease((t - 5.0) / 1.4)
    beat = 1 + 0.06 * max(0, math.sin(t * 5)) * (1 - morph)
    appear = ease(t / 1.6)
    for k in range(N_STARS):
        (hx, hy), (qx, qy) = HEART[k], QMARK[k]
        x = (hx + (qx - hx) * morph) * beat
        y = (hy + (qy - hy) * morph) * beat
        # stars fly in from scattered positions
        sx, sy = math.cos(k * 2.4) * 1.6, math.sin(k * 1.7) * 1.0
        x, y = sx + (x - sx) * appear, sy + (y - sy) * appear
        r = 3 + 1.5 * math.sin(t * 4 + k)
        col = lerp((255, 90, 120), (255, 200, 120), morph)
        px, py = cx + x * sc, cy + y * sc
        d.ellipse([px - r, py - r, px + r, py + r], fill=col)
    # the orb (Claude) drifts in and circles it, a little shy
    orbit = ease((t - 0.5) / 2.0)
    ang = t * 0.9
    ox = cx + math.cos(ang) * 260 * orbit + (1 - orbit) * 0
    oy = cy + math.sin(ang) * 70 * orbit + (1 - orbit) * 360
    for r, c in ((22, (120, 90, 160)), (13, (220, 210, 255)), (7, (255, 255, 255))):
        d.ellipse([ox - r, oy - r, ox + r, oy + r], fill=c)
    img = glow(img, layer, 9)
    d = ImageDraw.Draw(img)
    y = H * 0.72
    # captions come in beats; each new beat replaces the previous one
    beats = [[0], [1, 2], [3, 4]]
    current = [g for g in beats if t >= SECRET_TEXT[g[0]][0]]
    for j in (current[-1] if current else []):
        start, text, f, col = SECRET_TEXT[j]
        if t >= start:
            n = int((t - start) * 30)
            w = d.textlength(text, font=f)
            d.text(((W - w) / 2, y), text[:n], font=f, fill=col)
        y += f.size + 18
    fade_out = ease((t - dur + 0.8) / 0.8)
    fade_in = 1 - ease(t / 0.8)
    if fade_in > 0:
        img = Image.blend(img, Image.new("RGB", (W, H), (255, 246, 230)), fade_in)
    if fade_out > 0:
        img = Image.blend(img, Image.new("RGB", (W, H)), fade_out)
    return img


def draw_end_v2(t, dur):
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    a = ease(t / 0.8) * ease((dur - t) / 0.8)
    center_text(d, H / 2 - 50, "Thanks for flying with me.", F_H1, with_alpha((255, 255, 255), a))
    center_text(d, H / 2 + 20, "Keep the questions coming.", F_H2, with_alpha((255, 200, 120), a))
    return img


# ---------------------------------------------------------------- audio
def make_audio(scenes, path):
    total = sum(d for d, _ in scenes)
    n = int(total * SR)
    t = np.arange(n) / SR
    lfo = 0.5 + 0.5 * np.sin(2 * np.pi * 0.08 * t)
    out = sum(np.sin(2 * np.pi * f * t) * a for f, a in
              [(55, 0.3), (82.5, 0.18), (110, 0.12), (164.8, 0.06 * lfo)]) * (0.6 + 0.4 * lfo)
    flight0 = scenes[0][0]
    secret0 = flight0 + scenes[1][0]

    def add(start, length, wave_fn, attack, decay, gain):
        i0, i1 = int(start * SR), min(n, int((start + length) * SR))
        tt = np.arange(i1 - i0) / SR
        out[i0:i1] += wave_fn(tt) * np.minimum(tt / attack, 1) * np.exp(-tt / decay) * gain

    rng = np.random.default_rng(1)
    for i in range(len(ROOMS)):  # whoosh + chime entering each room
        s = flight0 + i * ROOM_SECS + 0.4
        noise = np.convolve(rng.normal(0, 1, int(2 * SR)), np.ones(40) / 40, mode="same")
        add(s, 2.0, lambda tt, nz=noise: nz[:len(tt)], 0.4, 0.5, 0.7)
        add(s + 0.6, 2.5, lambda tt, f=440 + 55 * i: np.sin(2 * np.pi * f * tt), 0.01, 0.8, 0.08)
    corridor = flight0 + ROOM_SECS * len(ROOMS)
    for b in np.arange(corridor, secret0 - 1.5, 0.8):  # heartbeat
        for off in (0, 0.18):
            add(b + off, 0.3, lambda tt: np.sin(2 * np.pi * 50 * tt), 0.005, 0.07, 1.4)
    add(secret0 - 1.6, 1.4, lambda tt: np.sin(2 * np.pi * (120 + 60 * tt) * tt + 3 * np.sin(2 * np.pi * 9 * tt)),
        0.2, 0.6, 0.25)
    add(secret0, 8.0, lambda tt: sum(np.sin(2 * np.pi * f * tt) for f in (523.3, 659.3, 784.0)), 0.05, 3.0, 0.06)
    add(secret0 + 6.4, 6.0, lambda tt: sum(np.sin(2 * np.pi * f * tt) for f in (587.3, 740.0, 880.0, 1174.7)),
        0.05, 2.5, 0.06)
    out *= np.minimum(1, np.minimum(t / 1.5, (total - t) / 2.0))
    out = out / np.max(np.abs(out)) * 0.7
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes((out * 32767).astype(np.int16).tobytes())


def timeline():
    world = build_world()
    return [(4.5, draw_title), (FLIGHT_SECS, make_flight(world)), (17.0, draw_secret), (3.0, draw_end_v2)]


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "claude_brain_flythrough.mp4"
    scenes = timeline()
    wav = out.rsplit(".", 1)[0] + ".wav"
    make_audio(scenes, wav)
    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", wav,
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "medium",
         "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", out],
        stdin=subprocess.PIPE,
    )
    for dur, fn in scenes:
        for f in range(int(round(dur * FPS))):
            proc.stdin.write(fn(f / FPS, dur).tobytes())
    proc.stdin.close()
    proc.wait()
    print(f"wrote {out} ({sum(d for d, _ in scenes):.1f}s)")


if __name__ == "__main__":
    main()
