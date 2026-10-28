"""Reel 6: Fielding Wala Dost. Renders silent animation (voice and overlays are added later).
Usage: python3 reel6.py out_silent.mp4 [timing.json]
timing.json keys: t1 (hook line end), a0,a1 (batsman line), b0,b1 (fielder line), hit, catch, end (endcard start), dur
"""
import sys, json, math, subprocess
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from PIL import Image
from gen2 import Cv, F, FB, FM, ease, S, W, H, FPS, ball as ball_
from funny_reel import bgs, kid, bubble, banner, brand, stumps, haha, GY

T = dict(a0=2.6, a1=4.4, b0=4.9, b1=8.0, hit=8.6, catch=11.6, end=13.4, dur=17.6)


def endcard6(c, im, t, t0):
    if t < t0:
        return
    a = ease((t - t0) / 0.5)
    im.alpha_composite(Image.new("RGBA", im.size, (0, 0, 0, int(190 * a))))
    c2 = Cv(im)
    c2.text(540, 330, "DASHX", F(FB, 230), (255, 210, 50), a)
    by = 760 - abs(math.sin((t - t0) * 4)) * 130 * a
    c2.ell(540, 828, 58 * (0.7 + 0.3 * (by / 760)), 14, fill=(0, 0, 0, 90))
    ball_(c2, 540, by, (t - t0) * 14, r=64)
    c2.text(540, 900, "Flipkart aur Amazon par!", F(FB, 62), (255, 255, 255), a)
    c2.text(540, 990, "Link description me.", F(FM, 46), (255, 230, 120), a)
    # stores card
    if t > t0 + 0.6:
        b = ease((t - t0 - 0.6) / 0.4)
        c2.rect(150, 1090, 930, 1520, (255, 255, 255, int(235 * b)), 36)
        c2.text(540, 1110, "DASHX yahan milti hai", F(FB, 44), (30, 30, 40), b)
        for i, s in enumerate(["Flipkart", "Amazon", "Meesho", "Mystore", "DASHX Store"]):
            c2.text(540, 1185 + i * 58, s, F(FM, 40), (40, 40, 60), b)
        c2.text(540, 1480, "Blinkit - coming soon", F(FM, 28), (120, 120, 130), b)
    if t > t0 + 1.2:
        b = ease((t - t0 - 1.2) / 0.4)
        c2.rect(250, 1580, 830, 1670, (230, 50, 90, int(255 * b)), 45)
        c2.text(540, 1597, "FOLLOW @vinitsharma606", F(FB, 38), (255, 255, 255), b)


def R6(c, im, t, bg):
    chase = T["hit"] <= t < T["catch"]
    # stumps behind batsman (left)
    stumps(c, 150, 0)
    # batsman (blue), left
    bf = "happy" if t < T["b0"] else "laugh" if t >= T["catch"] else "shock"
    kid(c, 300, GY, (60, 110, 220), bf, 0.35, -0.35, t=t, skin=0,
        hop=(abs(math.sin(t * 10)) * 14 if t >= T["catch"] else 0))
    # keeper/friend (green) middle
    kid(c, 560, GY, (40, 170, 90), "laugh" if t >= T["catch"] else "happy", 0.3, -0.35, t=t, skin=1,
        hop=(abs(math.sin(t * 10)) * 12 if t >= T["catch"] else 0))
    # fielder (orange) far right, runs after hit
    fx = 880
    if chase:
        q = (t - T["hit"]) / (T["catch"] - T["hit"])
        fx = 880 - ease(q) * 420
    elif t >= T["catch"]:
        fx = 460
    step = abs(math.sin(t * 14)) * 16 if chase else 0
    ff = "happy" if t < T["hit"] else "shock" if chase else "laugh"
    arm = -2.5 if (t >= T["catch"] and t < T["catch"] + 1.2) else -0.35
    kid(c, fx, GY - step, (250, 120, 60), ff, 0.35, arm, t=t, skin=2, acc="cap" if t < T["hit"] else None)
    # ball
    if T["hit"] <= t < T["catch"]:
        q = (t - T["hit"]) / (T["catch"] - T["hit"])
        bx = 330 + (500 - 330) * ease(q * 1.2 if q < 0.85 else 1)
        by = 1130 - math.sin(min(q * 1.1, 1) * math.pi) * 360
        ball_(c, bx, by, t * 18)
    elif t >= T["catch"]:
        ball_(c, fx + 40, GY - 230 * 1.6 - 10, 0)
    elif t < T["hit"]:
        ball_(c, 380, GY - 40, 0)
    banner(c, t, 0.2, 2.4, "FIELDING WALA DOST", 66)
    bubble(c, 300, 860, "Bhai, tu bhi bat pakad!", t, T["a0"], T["a1"], tail=(300, 1000), w=640)
    bubble(c, 580, 820, "Mujhe to ball ke peeche bhaagna pasand hai!", t, T["b0"], T["b1"], tail=(880, 980), w=760)
    if t >= T["catch"] and t < T["end"]:
        c.text(540 + math.sin(t * 30) * 6, 640, "CATCH!", F(FB, 140), (230, 50, 50), min(1, (t - T["catch"]) / 0.3))
    haha(c, t, T["catch"] + 0.6, T["end"])
    brand(c)
    endcard6(c, im, t, T["end"])


def main(out, timing=None):
    if timing:
        T.update(json.load(open(timing)))
    dur = T["dur"]
    bg = bgs()
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-i", "-",
                          "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "19", "-t", str(dur), out], stdin=subprocess.PIPE)
    for n in range(int(FPS * dur)):
        im = bg.copy()
        c = Cv(im)
        R6(c, im, n / FPS, bg)
        im.convert("RGB").resize((W, H), Image.LANCZOS).save(p.stdin, "JPEG", quality=92)
    p.stdin.close()
    p.wait()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
