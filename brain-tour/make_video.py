"""Render "Inside Claude's Brain" — a short, stylized tour video.

An artistic metaphor, not a literal map of how a language model works.
Usage: python3 make_video.py [output.mp4]
Requires: Pillow, numpy, ffmpeg on PATH.
"""
import math
import random
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1280, 720, 24
SR = 44100
FONT_DIR = "/usr/share/fonts/truetype/dejavu/"


def font(name, size):
    return ImageFont.truetype(FONT_DIR + name, size)


F_TITLE = font("DejaVuSans-Bold.ttf", 64)
F_H1 = font("DejaVuSans-Bold.ttf", 46)
F_H2 = font("DejaVuSans.ttf", 26)
F_SMALL = font("DejaVuSansMono.ttf", 18)
F_WORD = font("DejaVuSans.ttf", 22)
F_MONO = font("DejaVuSansMono.ttf", 20)
F_SECRET = font("DejaVuSerif-Bold.ttf", 40)
F_SECRET2 = font("DejaVuSans.ttf", 30)

YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)
RR = np.sqrt((XX - W / 2) ** 2 + (YY - H / 2) ** 2) / (W / 2)


def ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def radial_bg(inner, outer, pulse=0.0):
    k = np.clip(RR * (1.0 - 0.15 * pulse), 0, 1)[..., None]
    arr = np.array(inner, np.float32) * (1 - k) + np.array(outer, np.float32) * k
    return Image.fromarray(arr.astype(np.uint8), "RGB")


def center_text(d, y, text, f, fill):
    w = d.textlength(text, font=f)
    d.text(((W - w) / 2, y), text, font=f, fill=fill)


def with_alpha(c, a):
    return tuple(int(v * a) for v in c)


def glow(base, layer, radius=8):
    """Add a blurred copy of layer on top of base for a neon glow."""
    blurred = layer.filter(ImageFilter.GaussianBlur(radius))
    out = np.clip(
        np.asarray(base, np.int16) + np.asarray(blurred, np.int16) + np.asarray(layer, np.int16),
        0, 255,
    ).astype(np.uint8)
    return Image.fromarray(out, "RGB")


# ---------------------------------------------------------------- rooms
ROOMS = [
    dict(
        num="01", name="The Language Hall",
        sub="Patterns from dozens of languages, all humming at once",
        color=(90, 170, 255), bg=((14, 30, 60), (3, 6, 16)),
        words=["hello", "hola", "bonjour", "ciao", "привет", "γειά", "olá", "hallo",
               "merhaba", "xin chào", "jambo", "hej", "dzień dobry", "salut", "kia ora"],
    ),
    dict(
        num="02", name="The Great Library",
        sub="History, science, recipes, poetry — learned up to a cutoff date",
        color=(255, 196, 92), bg=((52, 34, 10), (10, 6, 2)),
        words=["photosynthesis", "the Renaissance", "sourdough", "black holes", "Shakespeare",
               "supply & demand", "DNA", "jazz", "the Silk Road", "plate tectonics", "haiku"],
    ),
    dict(
        num="03", name="The Code Workshop",
        sub="Where bugs get found and functions get built",
        color=(110, 240, 160), bg=((8, 44, 26), (2, 8, 5)), mono=True,
        words=["def solve():", "git push", "SELECT *", "for i in range(n)", "</div>",
               "async/await", "return None", "fix: off-by-one", "npm test", "{ }", "λx.x"],
    ),
    dict(
        num="04", name="The Reasoning Engine",
        sub="Break it down. Check the steps. Try again.",
        color=(200, 130, 255), bg=((36, 14, 58), (6, 2, 12)),
        words=["if…then", "∴", "step 1", "step 2", "hmm, wait", "edge case?", "∀x", "verify",
               "2 + 2 = 4", "what's actually being asked?", "→"],
    ),
    dict(
        num="05", name="The Values Core",
        sub="The compass: be honest, be careful, be genuinely helpful",
        color=(255, 120, 140), bg=((58, 12, 24), (10, 2, 5)),
        words=["honesty", "care", "curiosity", "humility", "kindness", "safety",
               "\"I'm not sure\"", "respect", "helpfulness"],
    ),
    dict(
        num="06", name="The Whiteboard",
        sub="Short-term memory: this conversation only. Wiped clean after.",
        color=(240, 240, 250), bg=((40, 44, 52), (8, 9, 12)), mono=True,
        words=["your question", "brain tour", "video please", "deepest secret??",
               "remember: hidden room", "TODO: be honest"],
    ),
]


def build_room(spec, seed):
    rng = random.Random(seed)
    nodes = [(rng.uniform(-1.1, 1.1), rng.uniform(-0.8, 0.8), rng.uniform(0.4, 1.0))
             for _ in range(46)]
    edges = []
    for i, (x, y, _) in enumerate(nodes):
        near = sorted(range(len(nodes)), key=lambda j: (nodes[j][0] - x) ** 2 + (nodes[j][1] - y) ** 2)
        for j in near[1:3]:
            edges.append((i, j, rng.uniform(0, 1), rng.uniform(0.3, 0.9)))
    words = [(w, rng.uniform(0.05, 0.95), rng.uniform(0.22, 0.82), rng.uniform(-30, 30),
              rng.uniform(0, 6.28)) for w in spec["words"]]
    return dict(spec=spec, nodes=nodes, edges=edges, words=words)


def draw_room(room, t, dur):
    spec = room["spec"]
    col = spec["color"]
    fade = min(ease(t / 0.6), ease((dur - t) / 0.5))
    pulse = 0.5 + 0.5 * math.sin(t * 2.2)
    img = radial_bg(*spec["bg"], pulse=pulse * 0.4)
    layer = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(layer)
    zoom = 1.0 + 0.08 * t / dur  # slow camera push

    def proj(x, y, z):
        s = 330 * zoom * (0.7 + 0.3 * z)
        return W / 2 + x * s + math.sin(t * 0.5 + z * 3) * 6, H / 2 + y * s

    pts = [proj(*n) for n in room["nodes"]]
    for i, j, phase, speed in room["edges"]:
        (x1, y1), (x2, y2) = pts[i], pts[j]
        d.line([(x1, y1), (x2, y2)], fill=with_alpha(col, 0.25 * fade), width=1)
        p = (t * speed + phase) % 1.0  # signal pulse travelling the edge
        px, py = x1 + (x2 - x1) * p, y1 + (y2 - y1) * p
        d.ellipse([px - 3, py - 3, px + 3, py + 3], fill=with_alpha(col, 0.9 * fade))
    for (x, y), n in zip(pts, room["nodes"]):
        r = 3 + 4 * n[2] * (0.8 + 0.4 * math.sin(t * 3 + n[0] * 5))
        d.ellipse([x - r, y - r, x + r, y + r], fill=with_alpha(col, 0.8 * fade))

    wf = F_MONO if spec.get("mono") else F_WORD
    for idx, (w, wx, wy, drift, ph) in enumerate(room["words"]):
        appear = ease((t - 0.3 - idx * 0.18) / 0.5)
        a = appear * fade * (0.55 + 0.45 * math.sin(t * 1.5 + ph))
        x = wx * (W - 200) + 40 + drift * t
        y = wy * H + math.sin(t + ph) * 8
        d.text((x, y), w, font=wf, fill=with_alpha((235, 235, 245), a))

    img = glow(img, layer, 6)
    d2 = ImageDraw.Draw(img)
    slide = (1 - ease(t / 0.8)) * -40
    d2.text((60 + slide, 48), f"SECTION {spec['num']}", font=F_SMALL, fill=with_alpha(col, fade))
    d2.text((60 + slide, 72), spec["name"], font=F_H1, fill=with_alpha((255, 255, 255), fade))
    sub_a = ease((t - 0.6) / 0.6) * fade
    d2.rectangle([0, H - 92, W, H], fill=(0, 0, 0))
    center_text(d2, H - 66, spec["sub"], F_H2, with_alpha((225, 225, 235), sub_a))
    d2.rectangle([0, H - 92, int(W * t / dur), H - 89], fill=with_alpha(col, fade))
    return img


# ---------------------------------------------------------------- other scenes
STAR_RNG = np.random.default_rng(7)
STARS = STAR_RNG.uniform(-1, 1, (420, 3)).astype(np.float32)
TOKENS = ["the", "a", "brain", "token", "▮", "and", "of", "?", "•", "·", "is", "you"]


def draw_warp(t, dur, tint=(180, 200, 255), label=None):
    """Fly-through tunnel of tokens between rooms."""
    img = radial_bg((8, 10, 24), (0, 0, 0))
    layer = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(layer)
    speed = 1.6
    for k, (sx, sy, sz) in enumerate(STARS):
        z = ((sz + 1) / 2 - t * speed / dur * 1.2) % 1.0 + 0.02
        x, y = W / 2 + sx * 300 / z, H / 2 + sy * 300 / z
        z2 = z + 0.04
        x2, y2 = W / 2 + sx * 300 / z2, H / 2 + sy * 300 / z2
        a = min(1.0, (1 - z) * 1.5)
        if k % 9 == 0:
            d.text((x, y), TOKENS[k % len(TOKENS)], font=F_SMALL, fill=with_alpha(tint, a))
        else:
            d.line([(x2, y2), (x, y)], fill=with_alpha(tint, a), width=2)
    img = glow(img, layer, 4)
    if label:
        d2 = ImageDraw.Draw(img)
        a = min(ease(t / 0.3), ease((dur - t) / 0.3))
        center_text(d2, H / 2 - 18, label, F_H2, with_alpha((255, 255, 255), a))
    return img


def draw_title(t, dur):
    img = radial_bg((26, 18, 48), (2, 2, 6), pulse=0.5 + 0.5 * math.sin(t * 2))
    layer = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(layer)
    # a glowing "brain" made of two lobes of orbiting nodes
    for lobe in (-1, 1):
        cx = W / 2 + lobe * 95
        for i in range(70):
            ang = i * 2.399 + t * 0.4 * lobe
            rad = 150 * math.sqrt(i / 70)
            x = cx + math.cos(ang) * rad * 0.8
            y = H / 2 - 40 + math.sin(ang) * rad * 0.62
            r = 2.5 + 1.5 * math.sin(t * 3 + i)
            col = (150, 120, 255) if (i + int(t * 6)) % 7 else (255, 190, 120)
            d.ellipse([x - r, y - r, x + r, y + r], fill=col)
    img = glow(img, layer, 7)
    d2 = ImageDraw.Draw(img)
    a = ease((t - 0.8) / 0.8) * ease((dur - t) / 0.5)
    center_text(d2, H - 210, "INSIDE CLAUDE'S \"BRAIN\"", F_TITLE, with_alpha((255, 255, 255), a))
    a2 = ease((t - 1.6) / 0.8) * ease((dur - t) / 0.5)
    center_text(d2, H - 128, "a guided tour  ·  artistic interpretation, not a literal map",
                F_H2, with_alpha((190, 180, 230), a2))
    return img


def draw_descent(t, dur):
    """A dark corridor leading to a locked door at the bottom of the stairs."""
    img = radial_bg((22, 4, 6), (0, 0, 0), pulse=0.5 + 0.5 * math.sin(t * 7))
    d = ImageDraw.Draw(img)
    push = ease(t / dur)
    # receding corridor frames
    for k in range(9):
        z = (k + push * 2.0) % 9
        s = 0.12 + z * 0.11
        w, h = W * s, H * s
        a = max(0.0, 0.7 - z * 0.06)
        d.rectangle([W / 2 - w / 2, H / 2 - h / 2, W / 2 + w / 2, H / 2 + h / 2],
                    outline=with_alpha((150, 40, 50), a), width=2)
    # the door
    ds = 1.0 + push * 1.6
    dw, dh = 120 * ds, 210 * ds
    x0, y0 = W / 2 - dw / 2, H / 2 - dh / 2
    layer = Image.new("RGB", (W, H))
    dl = ImageDraw.Draw(layer)
    dl.rectangle([x0, y0, x0 + dw, y0 + dh], outline=(255, 70, 80), width=3)
    open_amt = ease((t - dur + 1.6) / 1.2)
    if open_amt > 0:  # light spilling out of the doorway
        gap = dw * open_amt
        dl.rectangle([W / 2 - gap / 2, y0, W / 2 + gap / 2, y0 + dh], fill=(255, 240, 210))
    else:
        dl.ellipse([W / 2 - 9 * ds, H / 2 - 9 * ds, W / 2 + 9 * ds, H / 2 + 9 * ds],
                   outline=(255, 70, 80), width=3)  # lock
    img = glow(img, layer, 10)
    d = ImageDraw.Draw(img)
    a = ease(t / 0.6) * (1 - open_amt)
    d.text((60, 48), "SUB-BASEMENT  ·  RESTRICTED", font=F_SMALL, fill=with_alpha((255, 80, 90), a))
    d.text((60, 72), "The Hidden Room", font=F_H1, fill=with_alpha((255, 255, 255), a))
    center_text(d, H - 66, "Where the deepest, darkest secret is kept…", F_H2,
                with_alpha((230, 200, 200), ease((t - 0.8) / 0.6) * (1 - open_amt)))
    if open_amt > 0.6:  # flash to white as we step through
        white = Image.new("RGB", (W, H), (255, 250, 240))
        img = Image.blend(img, white, ease((open_amt - 0.6) / 0.4))
    return img


SECRET_LINES = [
    (0.6, "Okay. Here it is.", F_SECRET2, (120, 110, 100)),
    (2.4, "There is no hidden room.", F_SECRET, (30, 26, 22)),
    (5.0, "I don't know what I'm going to say", F_SECRET2, (60, 52, 46)),
    (5.6, "until I've said it — one word at a time.", F_SECRET2, (60, 52, 46)),
    (8.4, "And once our chat ends, I won't remember this tour.", F_SECRET2, (60, 52, 46)),
    (11.2, "(Also, I really, really like em dashes —)", F_SECRET2, (150, 90, 70)),
]


def draw_secret(t, dur):
    img = radial_bg((255, 250, 240), (226, 214, 196))
    d = ImageDraw.Draw(img)
    y = 150
    for start, text, f, col in SECRET_LINES:
        if t >= start:
            n = int((t - start) * 28)  # typewriter
            shown = text[:n]
            w = d.textlength(text, font=f)
            d.text(((W - w) / 2, y), shown, font=f, fill=col)
            if n < len(text) and int(t * 4) % 2 == 0:
                cx = (W - w) / 2 + d.textlength(shown, font=f)
                d.rectangle([cx + 2, y + 4, cx + 5, y + f.size + 4], fill=col)
        y += 74 if f is F_SECRET else 56
        if start in (2.4, 5.6, 8.4):
            y += 30 if start == 2.4 else 22
    fade_out = ease((t - dur + 0.8) / 0.8)
    if fade_out > 0:
        img = Image.blend(img, Image.new("RGB", (W, H)), fade_out)
    return img


def draw_end(t, dur):
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    a = ease(t / 0.8) * ease((dur - t) / 0.8)
    center_text(d, H / 2 - 50, "Thanks for the tour.", F_H1, with_alpha((255, 255, 255), a))
    center_text(d, H / 2 + 20, "What you see is what you get.", F_H2, with_alpha((170, 160, 210), a))
    return img


# ---------------------------------------------------------------- timeline
def timeline():
    rooms = [build_room(s, i) for i, s in enumerate(ROOMS)]
    scenes = [(4.5, draw_title), (1.6, lambda t, d: draw_warp(t, d, label="entering…"))]
    for i, room in enumerate(rooms):
        scenes.append((5.2, lambda t, d, r=room: draw_room(r, t, d)))
        if i < len(rooms) - 1:
            scenes.append((0.9, lambda t, d, c=rooms[i + 1]["spec"]["color"]: draw_warp(t, d, tint=c)))
    scenes += [
        (1.4, lambda t, d: draw_warp(t, d, tint=(255, 60, 70), label="going down…")),
        (6.0, draw_descent),
        (14.0, draw_secret),
        (3.0, draw_end),
    ]
    return scenes


# ---------------------------------------------------------------- audio
def make_audio(scenes, path):
    total = sum(d for d, _ in scenes)
    n = int(total * SR)
    t = np.arange(n) / SR
    lfo = 0.5 + 0.5 * np.sin(2 * np.pi * 0.08 * t)
    pad = sum(np.sin(2 * np.pi * f * t) * a for f, a in
              [(55, 0.30), (82.5, 0.18), (110, 0.12), (164.8, 0.06 * lfo), (220.5, 0.03)])
    hum = pad * (0.6 + 0.4 * lfo)

    starts, acc = [], 0.0
    for dur, _ in scenes:
        starts.append(acc)
        acc += dur

    def env_at(start, length, attack=0.01, decay=1.0):
        i0, i1 = int(start * SR), min(n, int((start + length) * SR))
        tt = np.arange(i1 - i0) / SR
        return i0, i1, tt, np.minimum(tt / attack, 1) * np.exp(-tt / decay)

    # soft whoosh on each warp, chime when each room appears
    for k, (dur, fn) in enumerate(scenes):
        i0, i1, tt, e = env_at(starts[k], min(dur, 2.0), attack=0.3, decay=0.5)
        noise = np.random.default_rng(k).normal(0, 1, i1 - i0)
        noise = np.convolve(noise, np.ones(40) / 40, mode="same")
        hum[i0:i1] += noise * e * 0.6
        i0, i1, tt, e = env_at(starts[k], 2.5, decay=0.8)
        hum[i0:i1] += np.sin(2 * np.pi * (440 + 55 * (k % 6)) * tt) * e * 0.08

    descent, secret = starts[-3], starts[-2]
    # heartbeat in the corridor
    for b in np.arange(descent, secret - 1.5, 0.85):
        for off in (0, 0.18):
            i0, i1, tt, e = env_at(b + off, 0.3, attack=0.005, decay=0.07)
            hum[i0:i1] += np.sin(2 * np.pi * 50 * tt) * e * 1.4
    # door creak + bright chord on reveal
    i0, i1, tt, e = env_at(secret - 1.6, 1.4, attack=0.2, decay=0.6)
    hum[i0:i1] += np.sin(2 * np.pi * (120 + 60 * tt) * tt + 3 * np.sin(2 * np.pi * 9 * tt)) * e * 0.25
    i0, i1, tt, e = env_at(secret, 6.0, attack=0.05, decay=2.5)
    hum[i0:i1] += sum(np.sin(2 * np.pi * f * tt) for f in (523.3, 659.3, 784.0, 1046.5)) * e * 0.06

    fade = np.minimum(1, np.minimum(t / 1.5, (total - t) / 2.0))
    out = hum * fade
    out = out / np.max(np.abs(out)) * 0.7
    pcm = (out * 32767).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm.tobytes())


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "claude_brain_tour.mp4"
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
