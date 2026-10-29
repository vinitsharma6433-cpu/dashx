"""End card segment for the DASHX ground ad: dark overlay on the last scene frame, DASHX, Flipkart + Amazon, Follow pill.
Usage: python3 ad_end.py bg_frame.png out.mp4 [duration]
"""
import sys, math, subprocess
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from PIL import Image
from gen2 import Cv, F, FB, FM, ease, S, W, H, FPS, ball as ball_


def draw(base, t):
    im = base.copy()
    a = ease(t / 0.5)
    im.alpha_composite(Image.new("RGBA", im.size, (0, 0, 0, int(195 * a))))
    c = Cv(im)
    c.text(540, 300, "DASHX", F(FB, 230), (255, 210, 50), a)
    by = 760 - abs(math.sin(t * 4)) * 130 * a
    c.ell(540, 828, 58 * (0.7 + 0.3 * (by / 760)), 14, fill=(0, 0, 0, 90))
    ball_(c, 540, by, t * 14, r=64)
    c.text(540, 890, "Gali se ground tak!", F(FB, 56), (255, 255, 255), a)
    if t > 0.6:
        b = ease((t - 0.6) / 0.4)
        c.rect(150, 1010, 930, 1290, (255, 255, 255, int(235 * b)), 36)
        c.text(540, 1035, "DASHX yahan milti hai", F(FB, 46), (30, 30, 40), b)
        c.text(540, 1120, "Flipkart", F(FB, 58), (40, 90, 200), b)
        c.text(540, 1200, "Amazon", F(FB, 58), (230, 130, 20), b)
        c.text(540, 1330, "Link description me.", F(FM, 40), (255, 230, 120), a * b)
    if t > 1.2:
        b = ease((t - 1.2) / 0.4)
        c.rect(250, 1450, 830, 1540, (230, 50, 90, int(255 * b)), 45)
        c.text(540, 1467, "FOLLOW @vinitsharma606", F(FB, 38), (255, 255, 255), b)
    return im


def main(bg, out, dur=4.6):
    base = Image.open(bg).convert("RGB").resize((int(W * S), int(H * S)), Image.LANCZOS).convert("RGBA")
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-i", "-",
                          "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "19", "-t", str(dur), out], stdin=subprocess.PIPE)
    for n in range(int(FPS * dur)):
        draw(base, n / FPS).convert("RGB").resize((W, H), Image.LANCZOS).save(p.stdin, "JPEG", quality=92)
    p.stdin.close()
    p.wait()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 4.6)
