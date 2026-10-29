"""End card segment: dark overlay on the last scene frame, brand name, store list, Follow pill.
Usage: python3 ad_end.py bg_frame.png out.mp4 [duration] [config.json]
"""
import sys, json, math, subprocess
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from PIL import Image
from gen2 import Cv, F, FB, FM, ease, S, W, H, FPS, ball as ball_

STORE_COL = {"Flipkart": (40, 90, 200), "Amazon": (230, 130, 20)}
DEFAULT = dict(name="DASHX", end_tagline="Gali se ground tak!", stores=["Flipkart", "Amazon"],
               follow="@vinitsharma606", end_note="Link description me.")


def draw(base, t, b):
    im = base.copy()
    a = ease(t / 0.5)
    im.alpha_composite(Image.new("RGBA", im.size, (0, 0, 0, int(195 * a))))
    c = Cv(im)
    c.text(540, 300, b["name"], F(FB, 230 if len(b["name"]) <= 6 else 150), (255, 210, 50), a)
    by = 760 - abs(math.sin(t * 4)) * 130 * a
    c.ell(540, 828, 58 * (0.7 + 0.3 * (by / 760)), 14, fill=(0, 0, 0, 90))
    ball_(c, 540, by, t * 14, r=64)
    c.text(540, 890, b["end_tagline"], F(FB, 56), (255, 255, 255), a)
    st = b["stores"]
    if t > 0.6:
        k = ease((t - 0.6) / 0.4)
        bottom = 1010 + 120 + len(st) * 80
        c.rect(150, 1010, 930, bottom, (255, 255, 255, int(235 * k)), 36)
        c.text(540, 1035, b["name"] + " yahan milti hai", F(FB, 46), (30, 30, 40), k)
        for i, s in enumerate(st):
            c.text(540, 1120 + i * 80, s, F(FB, 58), STORE_COL.get(s, (40, 40, 60)), k)
        c.text(540, bottom + 40, b["end_note"], F(FM, 40), (255, 230, 120), a * k)
    if t > 1.2:
        k = ease((t - 1.2) / 0.4)
        y = 1010 + 120 + len(st) * 80 + 160
        c.rect(250, y, 830, y + 90, (230, 50, 90, int(255 * k)), 45)
        c.text(540, y + 17, "FOLLOW " + b["follow"], F(FB, 38), (255, 255, 255), k)
    return im


def main(bg, out, dur=4.6, cfg=None):
    b = dict(DEFAULT)
    if cfg:
        b.update({k: v for k, v in json.load(open(cfg)).get("brand", {}).items() if k in DEFAULT})
    base = Image.open(bg).convert("RGB").resize((int(W * S), int(H * S)), Image.LANCZOS).convert("RGBA")
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-i", "-",
                          "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "19", "-t", str(dur), out], stdin=subprocess.PIPE)
    for n in range(int(FPS * dur)):
        draw(base, n / FPS, b).convert("RGB").resize((W, H), Image.LANCZOS).save(p.stdin, "JPEG", quality=92)
    p.stdin.close()
    p.wait()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 4.6,
         sys.argv[4] if len(sys.argv) > 4 else None)
