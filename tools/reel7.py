"""Reel 7: Karwa Chauth special, DASHX ball hero. Renders the silent animation.
Usage: python3 reel7.py out_silent.mp4 [timing.json]
"""
import sys, json, math, random, subprocess
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from PIL import Image
from gen2 import Cv, F, FB, FM, ease, lerp, S, W, H, FPS, ball as ball_
from funny_reel import kid, bubble, brand, haha, GY

T = dict(hook0=0.3, kid0=5.96, kid1=8.26, card0=6.7, end=10.0, dur=17.4)
PACK = None


def bg7():
    im = Image.new("RGBA", (int(W * S), int(H * S)))
    c = Cv(im)
    for y in range(0, 1200, 6):
        c.rect(0, y, W, y + 7, lerp((12, 10, 48), (96, 40, 104), y / 1200))
    rnd = random.Random(7)
    for _ in range(110):
        c.ell(rnd.randint(0, W), rnd.randint(0, 760), rnd.choice((1.2, 1.8, 2.6)), fill=(255, 255, 255, 210))
    for r, a in ((190, 40), (150, 60), (120, 90)):
        c.ell(790, 330, r, fill=(255, 245, 200, a))
    c.ell(790, 330, 100, fill=(255, 248, 215, 255))
    c.ell(760, 305, 18, fill=(235, 225, 185, 255))
    c.ell(820, 360, 26, fill=(235, 225, 185, 255))
    c.ell(800, 290, 12, fill=(235, 225, 185, 255))
    hs = [(-20, 760, 280), (250, 690, 250), (500, 800, 300), (790, 720, 300)]
    for x, y, w in hs:
        c.rect(x, y, x + w, 1180, (28, 22, 58))
        for wx in range(int(x) + 36, int(x + w) - 70, 90):
            for wy in range(int(y) + 40, 1120, 120):
                if rnd.random() < 0.55:
                    c.rect(wx, wy, wx + 46, wy + 62, (255, 205, 95))
    c.rect(0, 1180, W, H, (122, 96, 82))
    c.rect(0, 1180, W, 1210, (170, 140, 120))
    for i in range(0, W + 120, 120):
        c.rect(i, 1100, i + 18, 1190, (186, 154, 132))
    c.rect(0, 1090, W, 1112, (186, 154, 132))
    for i in range(0, H - 1210, 90):
        c.rect(0, 1210 + i, W, 1213 + i, (104, 80, 68))
    return im


def diya(c, x, y, t, k):
    c.ell(x, y + 6, 46, 14, fill=(0, 0, 0, 80))
    c.d.pieslice([c.sx(x - 40), c.sx(y - 28), c.sx(x + 40), c.sx(y + 28)], 0, 180, fill=(196, 96, 42, 255))
    fl = 1 + 0.18 * math.sin(t * 11 + k * 2)
    c.ell(x, y - 26, 20 * fl, 34 * fl, fill=(255, 190, 70, 230))
    c.ell(x, y - 22, 10 * fl, 20 * fl, fill=(255, 245, 190, 255))
    c.ell(x, y - 24, 90, fill=(255, 190, 70, 38))


def chhalni(c, x, y, r=70):
    c.ell(x, y, r, fill=(255, 255, 255, 40), outline=(230, 190, 90), w=6)
    for k in range(-2, 3):
        c.line([(x - r * 0.9, y + k * r * 0.35), (x + r * 0.9, y + k * r * 0.35)], (230, 190, 90, 200), 2)
        c.line([(x + k * r * 0.35, y - r * 0.9), (x + k * r * 0.35, y + r * 0.9)], (230, 190, 90, 200), 2)


def cap(c, t, t0, t1, l1, l2=None, y=150):
    if not (t0 <= t < t1):
        return
    a = ease((t - t0) / 0.4) * (1 - ease((t - t1 + 0.4) / 0.4))
    h = 150 if l2 else 110
    c.rect(50, y, 1030, y + h, (0, 0, 0, int(160 * a)), 44)
    c.text(540, y + 14, l1, F(FB, 56), (255, 225, 90), a)
    if l2:
        c.text(540, y + 82, l2, F(FB, 52), (255, 255, 255), a)


def pack_card(im, t, t0, t1):
    global PACK
    if not (t0 <= t < t1):
        return
    if PACK is None:
        p = Image.open(__file__.rsplit('/tools', 1)[0] + "/gallery-11.jpg").convert("RGBA")
        PACK = p.resize((int(560 * S), int(560 * S * p.height / p.width)), Image.LANCZOS)
    f = 0.25 + 0.75 * ease((t - t0) / 0.5)
    f *= 1 + 0.015 * math.sin(t * 5)
    w, h = int(PACK.width * f), int(PACK.height * f)
    card = PACK.resize((w, h), Image.LANCZOS)
    glow = Image.new("RGBA", (w + 40, h + 40), (255, 215, 90, 120))
    im.alpha_composite(glow, (int(540 * S - w / 2 - 20), int(930 * S - h / 2 - 20)))
    im.alpha_composite(card, (int(540 * S - w / 2), int(930 * S - h / 2)))


def endcard7(c, im, t, t0):
    if t < t0:
        return
    a = ease((t - t0) / 0.5)
    im.alpha_composite(Image.new("RGBA", im.size, (0, 0, 0, int(195 * a))))
    c2 = Cv(im)
    c2.text(540, 300, "DASHX", F(FB, 230), (255, 210, 50), a)
    by = 760 - abs(math.sin((t - t0) * 4)) * 130 * a
    c2.ell(540, 828, 58 * (0.7 + 0.3 * (by / 760)), 14, fill=(0, 0, 0, 90))
    ball_(c2, 540, by, (t - t0) * 14, r=64)
    c2.text(540, 890, "Karwa Chauth ki shubhkamnayein!", F(FB, 50), (255, 255, 255), a)
    if t > t0 + 0.6:
        b = ease((t - t0 - 0.6) / 0.4)
        c2.rect(150, 1010, 930, 1290, (255, 255, 255, int(235 * b)), 36)
        c2.text(540, 1035, "DASHX yahan milti hai", F(FB, 46), (30, 30, 40), b)
        c2.text(540, 1120, "Flipkart", F(FB, 58), (40, 90, 200), b)
        c2.text(540, 1200, "Amazon", F(FB, 58), (230, 130, 20), b)
        c2.text(540, 1330, "Link description me.", F(FM, 40), (255, 230, 120), a * b)
    if t > t0 + 1.2:
        b = ease((t - t0 - 1.2) / 0.4)
        c2.rect(250, 1450, 830, 1540, (230, 50, 90, int(255 * b)), 45)
        c2.text(540, 1467, "FOLLOW @vinitsharma606", F(FB, 38), (255, 255, 255), b)


def R7(c, im, t, bg):
    k0, k1, c0 = T["kid0"], T["kid1"], T["card0"]
    for i, x in enumerate((110, 340, 720, 970)):
        diya(c, x, 1650, t, i)
    # aunty with chhalni (left), kid blue (middle), kid green (right)
    up = t < k0
    hands, _ = kid(c, 250, GY, (200, 40, 80), "happy", 0.35, -2.7 if up else -0.35, t=t, skin=2, k=1.7)
    if up:
        chhalni(c, hands[1][0] + 10, hands[1][1] - 40)
    thr = k0 <= t < k0 + 0.5
    kid(c, 620, GY, (60, 110, 220), "happy" if t < k0 else "laugh", 0.35, -2.5 if thr else -0.35, t=t, skin=0,
        hop=(abs(math.sin(t * 10)) * 12 if t >= c0 else 0))
    kid(c, 900, GY, (40, 170, 90), "shock" if k0 <= t < c0 + 0.6 else "happy", 0.3, -0.35, t=t, skin=1)
    # ball: sits at kid's feet, then flies up into the sky
    if t < k0:
        ball_(c, 700, GY - 30, 0)
    elif t < c0:
        q = (t - k0) / (c0 - k0)
        ball_(c, 620 + (540 - 620) * ease(q), 1180 - ease(q) * 620, t * 20, r=26 + 18 * q)
    cap(c, t, 0.2, 2.9, "KARWA CHAUTH SPECIAL")
    cap(c, t, 2.9, 5.6, "Chhalni se chaand dekha,", "ab DASHX se chauka!")
    bubble(c, 620, 880, "Lo bhaiya, ye rahi DASHX ball!", t, k0, k1, tail=(620, 1000), w=700)
    brand(c)
    pack_card(im, t, c0, T["end"] + 0.2)
    if c0 + 0.5 <= t < T["end"]:
        cc = Cv(im)
        cc.rect(240, 1500, 840, 1600, (0, 0, 0, 150), 40)
        cc.text(540, 1516, "DASHX POWER Cricket Tennis Ball", F(FB, 34), (255, 230, 90), 1.0)
    endcard7(Cv(im), im, t, T["end"])


def main(out, timing=None):
    if timing:
        T.update(json.load(open(timing)))
    bg = bg7()
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-i", "-",
                          "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "19", "-t", str(T["dur"]), out],
                         stdin=subprocess.PIPE)
    for n in range(int(FPS * T["dur"])):
        im = bg.copy()
        c = Cv(im)
        R7(c, im, n / FPS, bg)
        im.convert("RGB").resize((W, H), Image.LANCZOS).save(p.stdin, "JPEG", quality=92)
    p.stdin.close()
    p.wait()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
