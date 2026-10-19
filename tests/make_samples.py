"""Draws 3 DUMMY printed prescriptions into samples/ (no real patient data).
They are printed-style text, NOT handwriting. Add your own handwritten dummy photos too,
and list them in samples/answers.json, for a fair accuracy number."""
import os
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "samples")
RX = {
    "sample1.png": ["Tab Dolo 650 mg    1-0-1 after food   x 5 days", "Cap Omez 20 mg     1-0-0 before food  x 7 days"],
    "sample2.png": ["Tab Augmentin 625   BD after food     x 5 days", "Tab Pantop 40       OD before food     x 10 days",
                    "Tab Allegra 120mg   HS                x 5 days"],
    "sample3.png": ["Tab Glycomet 500    1-0-1 after food   x 30 days", "Tab Telma 40         OD                 x 30 days",
                    "Tab Ecosprin 75     OD after food      x 30 days", "Tab Azithral 500    OD after food      x 3 days"],
}


def font(size):
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", "DejaVuSansMono.ttf"]:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)


for fname, lines in RX.items():
    img = Image.new("RGB", (1100, 160 + 90 * len(lines)), "white")
    d = ImageDraw.Draw(img)
    d.text((40, 25), "Dr. Sample Doctor, MBBS  |  DUMMY PRESCRIPTION", fill="black", font=font(28))
    d.line((40, 80, 1060, 80), fill="black", width=2)
    d.text((40, 100), "Rx", fill="black", font=font(40))
    for i, line in enumerate(lines):
        d.text((120, 160 + 90 * i), line, fill="black", font=font(30))
    img.save(os.path.join(OUT, fname))
    print("wrote", fname)
