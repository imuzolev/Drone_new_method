#!/usr/bin/env python3
"""Generate QR code PNG textures for warehouse barcode placeholders.

Left rack (L): 24 QR codes encoding "God is good!"
Right rack (R): 24 QR codes encoding "All the time"
Each code has a unique ID embedded alongside the message.
"""

from pathlib import Path

import qrcode
from PIL import Image


OUTPUT_DIR = Path(__file__).resolve().parent.parent / "simulation" / "models" / "barcodes" / "textures"

SIDES: dict[str, str] = {
    "L": "God is good!",
    "R": "All the time",
}

SECTIONS = 12
LEVELS = 2
IMG_W, IMG_H = 400, 300


def generate_qr(data: str, path: Path) -> None:
    qr = qrcode.QRCode(
        version=2,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)

    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    canvas = Image.new("RGB", (IMG_W, IMG_H), "white")
    qr_w, qr_h = qr_img.size
    scale = min((IMG_W - 20) / qr_w, (IMG_H - 20) / qr_h)
    new_size = (int(qr_w * scale), int(qr_h * scale))
    qr_img = qr_img.resize(new_size, Image.LANCZOS)

    x_off = (IMG_W - new_size[0]) // 2
    y_off = (IMG_H - new_size[1]) // 2
    canvas.paste(qr_img, (x_off, y_off))

    canvas.save(path, "PNG")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    count = 0
    for side, message in SIDES.items():
        for section in range(1, SECTIONS + 1):
            for level in range(1, LEVELS + 1):
                label = f"barcode_{side}_{section:02d}_{level}"
                payload = f"{message} | {label}"
                filename = f"{label}.png"
                generate_qr(payload, OUTPUT_DIR / filename)
                count += 1

    print(f"Generated {count} QR code PNGs in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
