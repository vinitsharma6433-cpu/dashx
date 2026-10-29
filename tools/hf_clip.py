"""Free AI clip via Hugging Face Spaces: Qwen-Image-Fast (scene image) -> Wan 2.2 (image to video).
Runs in GitHub Actions. HF_TOKEN env is optional (a free token gives a bigger GPU quota).
Usage: python tools/hf_clip.py OUT_DIR "image prompt" "motion prompt"
"""
import os, sys, shutil, json, traceback
from gradio_client import Client, handle_file

IMG_SPACE = "mcp-tools/Qwen-Image-Fast"
VID_SPACE = "zerogpu-aoti/wan2-2-fp8da-aoti-faster"
TOKEN = os.environ.get("HF_TOKEN") or None


def pick_path(res):
    """Find a local file path in whatever the Space returned."""
    if isinstance(res, (list, tuple)):
        for r in res:
            p = pick_path(r)
            if p:
                return p
        return None
    if isinstance(res, dict):
        for k in ("video", "path", "url", "image"):
            if k in res and res[k]:
                return pick_path(res[k]) if isinstance(res[k], (dict, list, tuple)) else res[k]
        return None
    if isinstance(res, str) and os.path.exists(res):
        return res
    return None


def call(space, want, **kw):
    c = Client(space, hf_token=TOKEN) if TOKEN else Client(space)
    eps = c.view_api(return_format="dict")["named_endpoints"]
    name = next(iter(eps))
    names = {p["parameter_name"] for p in eps[name]["parameters"]}
    args = {k: v for k, v in kw.items() if k in names}
    print(space, name, "params:", sorted(names), "using:", sorted(args), flush=True)
    return pick_path(c.predict(api_name=name, **args))


def main(out, img_prompt, mot_prompt):
    os.makedirs(out, exist_ok=True)
    try:
        img = call(IMG_SPACE, "image", prompt=img_prompt, aspect_ratio="9:16",
                   num_inference_steps=8, randomize_seed=True)
        print("image:", img, flush=True)
        shutil.copy(img, os.path.join(out, "scene.png"))
        vid = call(VID_SPACE, "video", input_image=handle_file(img), prompt=mot_prompt,
                   duration_seconds=3.5, steps=6, randomize_seed=True)
        print("video:", vid, flush=True)
        shutil.copy(vid, os.path.join(out, "clip.mp4"))
    except Exception:
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
