"""DASHX reel maker: idea (prompt) or config -> finished vertical reel with voice.

  python3 tools/reelmaker/reelmaker.py --idea "Karwa Chauth special DASHX ad"
  python3 tools/reelmaker/reelmaker.py --config tools/reelmaker/configs/dashx_ground_ad.json

Stages: plan (free LLM writes the scenes, only for --idea) -> clips (Hugging Face image->video,
zoom/pan fallback) -> join (xfade) -> Hindi voice (Kokoro, offline) -> logo, pack card, captions,
end card -> social/<name>.mp4 + social/reels/<name>.json (title and caption for posting).
It never posts anything. Env: HF_TOKEN (optional but recommended), KOKORO_DIR (model cache).
"""
import os, sys, json, re, argparse, subprocess, shutil, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
XF = 0.3
MODELS = ["Qwen/Qwen2.5-72B-Instruct", "meta-llama/Llama-3.3-70B-Instruct", "Qwen/Qwen3-32B"]

PLAN_RULES = """You write a 5-scene vertical Instagram/YouTube Shorts ad for the cricket tennis ball brand DASHX
(Nav Durga Sports, Meerut, India). Reply with ONE JSON object only, no markdown, with keys:
name (short lowercase slug, letters and dashes), title (max 60 chars, Hinglish hook plus DASHX),
summary (one Hinglish line), end_voice (Devanagari, max 12 words, says the ball is on Flipkart and Amazon, link below, follow),
scenes: list of exactly 5 objects, each with:
 image (English visual prompt: a 3D Pixar-style scene with Indian kids in the same red and green t-shirts, a RED fuzzy tennis ball with a white seam, no text in the image),
 motion (English, what moves in the 3.5 second clip),
 caption (Hinglish in Roman letters, max 6 words),
 voice (Devanagari, max 7 words, easy to say in 3 seconds, the brand is written as डैश एक्स),
 voice_name (hm_omega or hm_psi).
Rules: scene 2 must be a close-up of the felt tennis ball. Use the given festival or topic naturally. No prices, no discounts,
no claims like best or number one, no specs, no real people, no other brands, no sensitive news."""


def sh(*a):
    subprocess.run([str(x) for x in a], check=True)


def dur(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p]).decode())


def load_cfg(path):
    base = json.load(open(os.path.join(HERE, "brand_dashx.json")))
    cfg = json.load(open(path))
    b = dict(base["brand"]); b.update(cfg.get("brand", {}))
    cfg["brand"] = b
    cfg.setdefault("links", base["links"])
    cfg.setdefault("style", base["style"])
    return cfg


# ---------- stage 1: plan (idea -> config) ----------
def plan(idea, out_cfg):
    tok = os.environ.get("HF_TOKEN")
    if not tok:
        sys.exit("plan needs HF_TOKEN (free Hugging Face token) to reach the free LLM")
    last = None
    for m in MODELS:
        try:
            body = json.dumps({"model": m, "max_tokens": 2500, "temperature": 0.7, "messages": [
                {"role": "system", "content": PLAN_RULES}, {"role": "user", "content": "Idea: " + idea}]}).encode()
            rq = urllib.request.Request("https://router.huggingface.co/v1/chat/completions", body,
                                        {"Authorization": "Bearer " + tok, "Content-Type": "application/json"})
            txt = json.load(urllib.request.urlopen(rq, timeout=180))["choices"][0]["message"]["content"]
            txt = re.sub(r"^```(?:json)?|```$", "", txt.strip(), flags=re.M).strip()
            cfg = json.loads(txt[txt.index("{"): txt.rindex("}") + 1])
            assert len(cfg["scenes"]) == 5 and all(k in s for s in cfg["scenes"] for k in ("image", "motion", "caption", "voice"))
            cfg["name"] = re.sub(r"[^a-z0-9-]+", "-", cfg.get("name", "reel").lower()).strip("-") or "reel"
            for s in cfg["scenes"]:
                s.setdefault("voice_name", "hm_omega")
            json.dump(cfg, open(out_cfg, "w"), indent=2, ensure_ascii=False)
            print("plan ok with", m, flush=True)
            return out_cfg
        except Exception as e:
            last = e
            print("plan failed with", m, repr(e)[:200], flush=True)
    sys.exit("plan failed on all models: %r" % (last,))


# ---------- stage 2: clips ----------
def zoom_clip(img, out):
    sh("ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", img, "-vf",
       "scale=1280:2304:flags=lanczos,zoompan=z='1+0.0011*on':x='iw/2-(iw/zoom/2)':y='ih*0.45-(ih/zoom*0.45)':d=57:s=480x832:fps=16,format=yuv420p",
       "-frames:v", "57", "-c:v", "libx264", "-crf", "18", out)


def clips(cfg, cdir, use_hf=True):
    os.makedirs(cdir, exist_ok=True)
    out = []
    for i, s in enumerate(cfg["scenes"], 1):
        cp, ip = os.path.join(cdir, "clip_%d.mp4" % i), os.path.join(cdir, "scene_%d.png" % i)
        if not os.path.exists(cp) and use_hf:
            try:
                from hf_clip import call, IMG_SPACE, VID_SPACE
                from gradio_client import handle_file
                if not os.path.exists(ip):
                    img = call(IMG_SPACE, "image", prompt=s["image"] + ". " + cfg["style"], aspect_ratio="9:16",
                               num_inference_steps=8, randomize_seed=True)
                    shutil.copy(img, ip)
                v = call(VID_SPACE, "video", input_image=handle_file(ip), prompt=s["motion"],
                         duration_seconds=3.5, steps=6, randomize_seed=True)
                shutil.copy(v, cp)
            except Exception as e:
                print("scene", i, "HF failed:", repr(e)[:160], flush=True)
        if not os.path.exists(cp) and os.path.exists(ip):
            print("scene", i, "using zoom fallback", flush=True)
            zoom_clip(ip, cp)
        if not os.path.exists(cp):
            sys.exit("scene %d has no clip or image" % i)
        out.append(cp)
    return out


# ---------- stage 3: join ----------
def join(cps, work):
    norm = []
    for i, c in enumerate(cps, 1):
        o = os.path.join(work, "n%d.mp4" % i)
        sh("ffmpeg", "-y", "-loglevel", "error", "-i", c, "-vf",
           "scale=1108:1920:flags=lanczos,crop=1080:1920,unsharp=5:5:0.6,fps=24,setsar=1,format=yuv420p",
           "-an", "-c:v", "libx264", "-crf", "18", o)
        norm.append(o)
    D = [dur(n) for n in norm]
    f, off, last = "", 0.0, "[0:v]"
    for i in range(1, len(norm)):
        off += D[i - 1] - XF
        f += "%s[%d:v]xfade=transition=fade:duration=%s:offset=%.4f[x%d];" % (last, i, XF, off, i)
        last = "[x%d]" % i
    body = os.path.join(work, "body.mp4")
    ins = sum([["-i", n] for n in norm], [])
    sh("ffmpeg", "-y", "-loglevel", "error", *ins, "-filter_complex", f.rstrip(";"), "-map", last,
       "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", body)
    starts = [0.0]
    for i in range(1, len(norm)):
        starts.append(starts[-1] + D[i - 1] - XF)
    return body, norm, starts


# ---------- stage 4: voice ----------
def kokoro_files():
    d = os.environ.get("KOKORO_DIR") or os.path.join(TOOLS, ".kokoro")
    os.makedirs(d, exist_ok=True)
    for f in ("kokoro-v1.0.onnx", "voices-v1.0.bin"):
        p = os.path.join(d, f)
        if not os.path.exists(p):
            print("downloading", f, flush=True)
            urllib.request.urlretrieve("https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/" + f, p)
    return os.path.join(d, "kokoro-v1.0.onnx"), os.path.join(d, "voices-v1.0.bin")


def voice(cfg, starts, end0, work):
    import numpy as np, soundfile as sf
    from kokoro_onnx import Kokoro
    k = Kokoro(*kokoro_files())
    sr = 24000
    segs = []
    for s, t0 in zip(cfg["scenes"], starts):
        segs.append((s["voice"], s.get("voice_name", "hm_omega"), t0 + 0.2))
    segs.append((cfg["end_voice"], "hm_omega", end0 + 0.5))
    audio = [(k.create(t, voice=v, speed=1.0, lang="hi")[0], t0) for t, v, t0 in segs]
    end_len = len(audio[-1][0]) / sr
    total = end0 + 0.5 + end_len + 1.0
    buf = np.zeros(int(total * sr) + sr)
    for a, t0 in audio:
        i = int(t0 * sr)
        buf[i:i + len(a)] += a
    p = os.path.join(work, "voice.wav")
    sf.write(p, buf, sr)
    return p, total


# ---------- stage 5: overlays, end card, mix ----------
def finish(cfg, body, norm, starts, wav, total, work, final):
    import gen2
    b = cfg["brand"]
    end0 = dur(body)
    last = os.path.join(work, "last.png")
    sh("ffmpeg", "-y", "-loglevel", "error", "-sseof", "-0.1", "-i", norm[-1], "-frames:v", "1", last)
    sh(sys.executable, "-I", os.path.join(TOOLS, "ad_end.py"), last, os.path.join(work, "end.mp4"), "%.2f" % (total - end0),
       os.path.join(work, "cfg.json"))
    from PIL import Image
    im = Image.open(os.path.join(ROOT, b["pack_card"])).convert("RGB")
    w = 220
    im = im.resize((w, int(im.height * w / im.width)), Image.LANCZOS)
    card = Image.new("RGB", (w + 12, im.height + 12), (255, 255, 255)); card.paste(im, (6, 6))
    cardp = os.path.join(work, "card.png"); card.save(cardp)
    dt = []
    for i, (s, t0) in enumerate(zip(cfg["scenes"], starts)):
        tf = os.path.join(work, "cap%d.txt" % i); open(tf, "w").write(s["caption"])
        dt.append("drawtext=fontfile=%s:textfile=%s:fontsize=54:fontcolor=white:borderw=4:bordercolor=black:box=1:"
                  "boxcolor=black@0.45:boxborderw=22:x=(w-text_w)/2:y=1330:enable='between(t,%.2f,%.2f)'"
                  % (gen2.FB, tf, t0 + 0.2, t0 + 3.4))
    fv = ("[1:v]scale=130:-1[lg];[0:v][lg]overlay=18:18[a1];[a1][2:v]overlay=W-w-24:H-h-60:enable='between(t,%.2f,%.2f)'[a2];[a2]%s[vb]"
          % (starts[1], end0, ",".join(dt)))
    sh("ffmpeg", "-y", "-loglevel", "error", "-i", body, "-i", os.path.join(ROOT, b["logo"]), "-i", cardp,
       "-filter_complex", fv, "-map", "[vb]", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", os.path.join(work, "body_ov.mp4"))
    sh("ffmpeg", "-y", "-loglevel", "error", "-i", os.path.join(work, "body_ov.mp4"), "-i", os.path.join(work, "end.mp4"),
       "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]", "-map", "[v]", "-c:v", "libx264", "-crf", "19", "-pix_fmt", "yuv420p",
       os.path.join(work, "video.mp4"))
    T = dur(os.path.join(work, "video.mp4"))
    tada = "+".join("if(gte(t,%.2f),0.35*sin(2*PI*%d*(t-%.2f))*exp(-5*(t-%.2f)),0)" % (end0 + o, fq, end0 + o, end0 + o)
                    for fq, o in ((523, 0), (659, .12), (784, .24), (1046, .4)))
    fa = ("aevalsrc='%s':s=44100:d=%.2f[cue];[0:a]aresample=44100,volume=1.2[vo];[cue]volume=0.3[c];"
          "[vo][c]amix=inputs=2:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11,afade=t=out:st=%.2f:d=0.5[a]" % (tada, T, T - 0.5))
    sh("ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-i", os.path.join(work, "video.mp4"), "-filter_complex", fa,
       "-map", "1:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-t", "%.2f" % T, final)


def meta(cfg, path):
    b = cfg["brand"]
    lines = [cfg["summary"], b["by"], ""] + ["%s par: %s" % (s, cfg["links"][s]) for s in b["stores"] if s in cfg["links"]]
    lines += ["", "Follow " + b["follow"], b["hashtags"] + " #Shorts"]
    json.dump({"yt_title": (cfg["title"] + " | #Shorts")[:95], "caption_youtube": "\n".join(lines),
               "caption_instagram": cfg["summary"] + "\n" + b["by"] + " Links: bio me.\n\n" + b["hashtags"] + " #CricketReels"},
              open(path, "w"), indent=2, ensure_ascii=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--idea"); ap.add_argument("--config"); ap.add_argument("--no-hf", action="store_true")
    ap.add_argument("--plan-only", action="store_true", help="only write the scenes with the free LLM, then stop")
    ap.add_argument("--work", default=os.path.join(ROOT, ".work"))
    a = ap.parse_args()
    if not (a.idea or a.config):
        sys.exit("give --idea or --config")
    os.makedirs(a.work, exist_ok=True)
    cpath = a.config
    if a.idea:
        cpath = plan(a.idea, os.path.join(a.work, "planned.json"))
        if a.plan_only:
            os.makedirs(os.path.join(ROOT, "social", "reels"), exist_ok=True)
            dst = os.path.join(ROOT, "social", "reels", json.load(open(cpath))["name"] + "-plan.json")
            shutil.copy(cpath, dst)
            print("PLAN saved", dst)
            return
    cfg = load_cfg(cpath)
    name = cfg["name"]
    work = os.path.join(a.work, name); os.makedirs(work, exist_ok=True)
    json.dump(cfg, open(os.path.join(work, "cfg.json"), "w"), ensure_ascii=False)
    cdir = os.path.join(ROOT, cfg.get("clips_dir", "social/reels/" + name + "-clips"))
    cps = clips(cfg, cdir, use_hf=not a.no_hf)
    body, norm, starts = join(cps, work)
    wav, total = voice(cfg, starts, dur(body), work)
    final = os.path.join(ROOT, "social", name + ".mp4")
    finish(cfg, body, norm, starts, wav, total, work, final)
    os.makedirs(os.path.join(ROOT, "social", "reels"), exist_ok=True)
    meta(cfg, os.path.join(ROOT, "social", "reels", name + ".json"))
    print("DONE", final, "%.1fs" % dur(final))


if __name__ == "__main__":
    main()
