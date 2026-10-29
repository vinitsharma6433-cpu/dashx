"""Make N scene clips with free Hugging Face Spaces (image -> video). Runs in GitHub Actions.
Usage: python tools/hf_ad.py tools/scenes_ad.json OUT_DIR
Writes OUT_DIR/scene_i.png and OUT_DIR/clip_i.mp4 for each scene that succeeds.
"""
import os, sys, json, shutil, time, traceback
sys.path.insert(0, os.path.dirname(__file__))
from gradio_client import Client, handle_file
from hf_clip import call, IMG_SPACE, VID_SPACE


def retry(fn, tries=3, wait=25):
    for i in range(tries):
        try:
            r = fn()
            if r:
                return r
        except Exception:
            traceback.print_exc()
        print("retry", i + 1, flush=True)
        time.sleep(wait)
    return None


def main(cfg, out):
    os.makedirs(out, exist_ok=True)
    d = json.load(open(cfg))
    ok = 0
    for i, s in enumerate(d["scenes"], 1):
        print("=== scene", i, flush=True)
        img = retry(lambda: call(IMG_SPACE, "image", prompt=s["image"] + ". " + d["style"], aspect_ratio="9:16",
                                 num_inference_steps=8, randomize_seed=True))
        if not img:
            continue
        shutil.copy(img, os.path.join(out, "scene_%d.png" % i))
        vid = retry(lambda: call(VID_SPACE, "video", input_image=handle_file(img), prompt=s["motion"],
                                 duration_seconds=3.5, steps=6, randomize_seed=True))
        if not vid:
            continue
        shutil.copy(vid, os.path.join(out, "clip_%d.mp4" % i))
        ok += 1
        print("scene", i, "done", flush=True)
    print("clips ok:", ok, "of", len(d["scenes"]), flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
