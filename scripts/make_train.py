#!/usr/bin/env python3
"""Build the tiny transparent login train (app/static/train.png).

The source frames in resources/ are opaque side-view scenes of a red locomotive +
hopper on a near-white background. We key the background to TRANSPARENT so the train
sits cleanly on the white login card with no visible box, then crop tight and scale
down small. The login CSS (.login-train) slowly chugs this single frame across the
card (a one-way translate, no bounce), so there is no sprite sheet to load.

Keying is a border-seeded flood fill (not a global white->alpha threshold) so the
locomotive's own white/cream body stripe is NOT punched out -- only background that
is connected to the image edge becomes transparent. The gray smoke is darker than
the fill threshold, so it survives as a faint plume.

Run from the repo root:  python scripts/make_train.py
Output: app/static/train.png  (referenced by .login-train in style.css)
"""
import glob
import re
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

OUT = Path("app/static/train.png")
FRAME = 1          # 1-based frame to use (small, neat smoke puff; train prominent)
THRESH = 60        # flood fill L1 color tolerance from the near-white border seed
PAD = 8            # px of transparent padding kept around the cropped train
DISP_W = 150       # on-screen width; rendered at 2x below for crisp display
SCALE = 2
_MAGENTA = (255, 0, 255)   # marker color absent from the source art


def _frames():
    files = glob.glob("resources/ChatGPT Image*.png")
    return sorted(files, key=lambda f: int(re.search(r"\((\d+)\)", f).group(1)))


def _keyed(path):
    """Return an RGBA image with the border-connected background made transparent."""
    im = Image.open(path).convert("RGB")
    w, h = im.size
    work = im.copy()
    # seed the flood from every border midpoint + corner so the whole surrounding
    # background fills regardless of where the train sits
    seeds = [(1, 1), (w - 2, 1), (1, h - 2), (w - 2, h - 2),
             (w // 2, 1), (w // 2, h - 2), (1, h // 2), (w - 2, h // 2)]
    for s in seeds:
        ImageDraw.floodfill(work, s, _MAGENTA, thresh=THRESH)
    r, g, b = work.split()
    # alpha = 0 exactly where the fill painted magenta, else fully opaque
    mr = r.point(lambda v: 255 if v == 255 else 0)
    mg = g.point(lambda v: 255 if v == 0 else 0)
    mb = b.point(lambda v: 255 if v == 255 else 0)
    bg = ImageChops.multiply(ImageChops.multiply(mr, mg), mb)
    alpha = ImageChops.invert(bg)
    out = im.convert("RGBA")
    out.putalpha(alpha)
    return out


def build():
    files = _frames()
    if not files:
        raise SystemExit("no resources/ChatGPT Image*.png frames found")
    img = _keyed(files[FRAME - 1])
    bbox = img.getchannel("A").getbbox()
    if bbox:
        l, t, r, b = bbox
        l, t = max(0, l - PAD), max(0, t - PAD)
        r, b = min(img.width, r + PAD), min(img.height, b + PAD)
        img = img.crop((l, t, r, b))
    tw = DISP_W * SCALE
    th = round(tw * img.height / img.width)
    img = img.resize((tw, th), Image.LANCZOS)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, optimize=True)
    print(f"train.png  native={tw}x{th}  display={DISP_W}x{th // SCALE}  "
          f"bytes={OUT.stat().st_size}")


if __name__ == "__main__":
    build()
