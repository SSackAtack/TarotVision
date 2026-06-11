"""Generate printable TarotVision A4 calibration target.

The target is intentionally marker-free: it does not contain ArUco markers, so
it cannot be confused with the table perspective markers.
"""

from __future__ import annotations

import argparse
import struct
import zlib
from pathlib import Path


A4_TARGET_WIDTH_PX = 2480
A4_TARGET_HEIGHT_PX = 3508
TARGET_VERSION = "tarotvision_calibration_target_a4_v1"
TARGET_TITLE = "TarotVision Calibration Target A4 v1"
DEFAULT_OUTPUT_PNG = "assets/calibration/tarotvision_calibration_target_a4.png"


def _font(size: int):
    return max(0.5, size / 32.0)


def generate_calibration_target_png(output_path: str) -> Path:
    try:
        return _generate_with_cv2(output_path)
    except Exception:
        return _generate_with_standard_library(output_path)


def _generate_with_cv2(output_path: str) -> Path:
    import cv2
    import numpy as np

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    image = np.ones((A4_TARGET_HEIGHT_PX, A4_TARGET_WIDTH_PX, 3), dtype=np.uint8) * 255
    margin = 175
    black = (0, 0, 0)

    def rect(x1, y1, x2, y2, color, thickness=-1):
        cv2.rectangle(image, (int(x1), int(y1)), (int(x2), int(y2)), color, thickness)

    def line(x1, y1, x2, y2, color=black, thickness=2):
        cv2.line(image, (int(x1), int(y1)), (int(x2), int(y2)), color, thickness, cv2.LINE_AA)

    def text(x, y, value, size=1.0, color=black, thickness=2):
        cv2.putText(image, value, (int(x), int(y)), cv2.FONT_HERSHEY_SIMPLEX, float(size), color, thickness, cv2.LINE_AA)

    # Outer border and corner geometry markers.
    rect(margin, margin, A4_TARGET_WIDTH_PX - margin, A4_TARGET_HEIGHT_PX - margin, black, 12)
    corner = 180
    for x, y in [
        (margin, margin),
        (A4_TARGET_WIDTH_PX - margin, margin),
        (margin, A4_TARGET_HEIGHT_PX - margin),
        (A4_TARGET_WIDTH_PX - margin, A4_TARGET_HEIGHT_PX - margin),
    ]:
        sx = 1 if x == margin else -1
        sy = 1 if y == margin else -1
        line(x, y, x + sx * corner, y, black, 22)
        line(x, y, x, y + sy * corner, black, 22)

    text(margin + 40, margin + 90, TARGET_TITLE, _font(72), black, 5)
    text(margin + 40, margin + 155, TARGET_VERSION, _font(28), black, 2)
    text(A4_TARGET_WIDTH_PX - margin - 360, margin + 90, "TOP", _font(72), black, 5)
    line(A4_TARGET_WIDTH_PX - margin - 210, margin + 150, A4_TARGET_WIDTH_PX - margin - 210, margin + 245, black, 14)
    line(A4_TARGET_WIDTH_PX - margin - 260, margin + 195, A4_TARGET_WIDTH_PX - margin - 210, margin + 145, black, 14)
    line(A4_TARGET_WIDTH_PX - margin - 160, margin + 195, A4_TARGET_WIDTH_PX - margin - 210, margin + 145, black, 14)

    # Checkerboard for focus.
    cb_x, cb_y = margin + 40, 450
    cell = 60
    for row in range(10):
        for col in range(10):
            fill = black if (row + col) % 2 == 0 else (255, 255, 255)
            rect(cb_x + col * cell, cb_y + row * cell, cb_x + (col + 1) * cell, cb_y + (row + 1) * cell, fill, -1)
    rect(cb_x, cb_y, cb_x + 10 * cell, cb_y + 10 * cell, black, 4)
    text(cb_x, cb_y + 10 * cell + 55, "Checkerboard / focus", _font(28), black, 2)

    # Thin and thick line sets.
    lx, ly = 980, 460
    for i, width in enumerate([1, 2, 3, 5, 8, 12]):
        y = ly + i * 70
        line(lx, y, lx + 520, y, black, width)
        text(lx + 550, y + 10, f"{width}px", _font(24), black, 2)
    for i in range(24):
        x = lx + i * 18
        line(x, ly + 470, x, ly + 720, black, 2)
    text(lx, ly + 790, "Fine vertical lines", _font(28), black, 2)

    # Slanted edge.
    sx, sy = 1650, 480
    cv2.fillPoly(image, [np.array([(sx, sy), (sx + 560, sy + 80), (sx + 560, sy + 520), (sx, sy + 440)], dtype=np.int32)], black)
    rect(sx - 5, sy - 5, sx + 565, sy + 525, black, 4)
    text(sx, sy + 590, "Slanted edge / sharpness", _font(28), black, 2)

    # Grayscale ramp.
    gx, gy = margin + 40, 1370
    steps = 11
    sw, sh = 180, 150
    for i in range(steps):
        value = int(255 * i / (steps - 1))
        rect(gx + i * sw, gy, gx + (i + 1) * sw, gy + sh, (value, value, value), -1)
        rect(gx + i * sw, gy, gx + (i + 1) * sw, gy + sh, black, 2)
        text(gx + i * sw + 45, gy + sh + 45, str(value), _font(22), black, 2)
    text(gx, gy - 45, "Grayscale / exposure", _font(32), black, 2)

    # Color patches and black/white fields.
    colors = [
        ("red", (30, 30, 220)),
        ("green", (70, 170, 30)),
        ("blue", (220, 80, 40)),
        ("yellow", (35, 220, 245)),
        ("cyan", (210, 200, 30)),
        ("magenta", (190, 40, 210)),
    ]
    cx, cy = margin + 40, 1670
    for i, (name, color) in enumerate(colors):
        x = cx + i * 330
        rect(x, cy, x + 250, cy + 180, color, -1)
        rect(x, cy, x + 250, cy + 180, black, 4)
        text(x, cy + 235, name, _font(26), black, 2)
    rect(cx, cy + 310, cx + 500, cy + 610, black, -1)
    rect(cx + 560, cy + 310, cx + 1060, cy + 610, (255, 255, 255), -1)
    rect(cx + 560, cy + 310, cx + 1060, cy + 610, black, 4)
    rect(cx + 1120, cy + 310, cx + 1780, cy + 610, (20, 20, 20), -1)
    rect(cx + 1120, cy + 310, cx + 1780, cy + 610, black, 4)
    text(cx + 1120, cy + 670, "Dark glare field", _font(28), black, 2)

    # Text at several sizes.
    tx, ty = margin + 40, 2450
    for label, size in [("8 pt", 22), ("10 pt", 28), ("12 pt", 34), ("16 pt", 46)]:
        text(tx, ty, f"{label}: TarotVision sharpness test 0123456789", _font(size), black, max(1, int(size / 20)))
        ty += size + 45

    # Dense micro-pattern.
    px, py = 1420, 2390
    for i in range(26):
        line(px, py + i * 16, px + 720, py + i * 16, black, 1)
    for i in range(46):
        line(px + i * 16, py, px + i * 16, py + 400, black, 1)
    rect(px, py, px + 720, py + 400, black, 3)
    text(px, py + 470, "Fine grid / contrast", _font(28), black, 2)

    cv2.imwrite(str(path), image)
    return path


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + chunk_type
        + data
        + struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
    )


def _write_rgb_png(path: Path, width: int, height: int, pixels: bytearray) -> None:
    raw_rows = []
    stride = width * 3
    for y in range(height):
        raw_rows.append(b"\x00" + bytes(pixels[y * stride:(y + 1) * stride]))
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(b"".join(raw_rows), level=6))
        + _png_chunk(b"IEND", b"")
    )
    path.write_bytes(png)


def _generate_with_standard_library(output_path: str) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    width = A4_TARGET_WIDTH_PX
    height = A4_TARGET_HEIGHT_PX
    pixels = bytearray([255]) * (width * height * 3)

    def set_px(x: int, y: int, color: tuple[int, int, int]) -> None:
        if 0 <= x < width and 0 <= y < height:
            idx = (y * width + x) * 3
            pixels[idx:idx + 3] = bytes(color)

    def rect(x1: int, y1: int, x2: int, y2: int, color: tuple[int, int, int], thickness: int = -1) -> None:
        x1, x2 = sorted((max(0, x1), min(width - 1, x2)))
        y1, y2 = sorted((max(0, y1), min(height - 1, y2)))
        if thickness < 0:
            for y in range(y1, y2 + 1):
                base = (y * width + x1) * 3
                row = bytes(color) * (x2 - x1 + 1)
                pixels[base:base + len(row)] = row
            return
        rect(x1, y1, x2, y1 + thickness, color, -1)
        rect(x1, y2 - thickness, x2, y2, color, -1)
        rect(x1, y1, x1 + thickness, y2, color, -1)
        rect(x2 - thickness, y1, x2, y2, color, -1)

    def hline(x1: int, x2: int, y: int, color: tuple[int, int, int], thickness: int = 1) -> None:
        rect(x1, y, x2, y + thickness, color, -1)

    def vline(x: int, y1: int, y2: int, color: tuple[int, int, int], thickness: int = 1) -> None:
        rect(x, y1, x + thickness, y2, color, -1)

    glyphs = {
        "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
        "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
        "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
        "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
        "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
        "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
        "G": ["01111", "10000", "10000", "10111", "10001", "10001", "01110"],
        "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
        "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
        "J": ["00111", "00010", "00010", "00010", "00010", "10010", "01100"],
        "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
        "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
        "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
        "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
        "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
        "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
        "Q": ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
        "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
        "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
        "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
        "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
        "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
        "W": ["10001", "10001", "10001", "10101", "10101", "10101", "01010"],
        "X": ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
        "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
        "Z": ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
        "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
        "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
        "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
        "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
        "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
        "5": ["11111", "10000", "10000", "11110", "00001", "00001", "11110"],
        "6": ["01111", "10000", "10000", "11110", "10001", "10001", "01110"],
        "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
        "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
        "9": ["01110", "10001", "10001", "01111", "00001", "00001", "11110"],
        "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
        ".": ["00000", "00000", "00000", "00000", "00000", "01100", "01100"],
        ":": ["00000", "01100", "01100", "00000", "01100", "01100", "00000"],
        "/": ["00001", "00010", "00010", "00100", "01000", "01000", "10000"],
    }

    def bitmap_text(x: int, y: int, value: str, scale: int, color: tuple[int, int, int]) -> None:
        cursor = x
        for char in value.upper():
            if char == " ":
                cursor += 4 * scale
                continue
            glyph = glyphs.get(char, glyphs["-"])
            for gy, row in enumerate(glyph):
                for gx, bit in enumerate(row):
                    if bit == "1":
                        rect(cursor + gx * scale, y + gy * scale, cursor + (gx + 1) * scale - 1, y + (gy + 1) * scale - 1, color, -1)
            cursor += 6 * scale

    def arrow_up(cx: int, y: int, scale: int, color: tuple[int, int, int]) -> None:
        vline(cx - scale // 2, y + 4 * scale, y + 11 * scale, color, scale)
        for i in range(5):
            hline(cx - i * scale, cx + i * scale, y + i * scale, color, scale)

    black = (0, 0, 0)
    margin = 175
    rect(margin, margin, width - margin, height - margin, black, 12)
    for x, y in [(margin, margin), (width - margin, margin), (margin, height - margin), (width - margin, height - margin)]:
        sx = 1 if x == margin else -1
        sy = 1 if y == margin else -1
        hline(x, x + sx * 180, y, black, 22)
        vline(x, y, y + sy * 180, black, 22)

    bitmap_text(margin + 40, 225, "TAROTVISION CALIBRATION TARGET A4 V1", 10, black)
    bitmap_text(margin + 40, 330, TARGET_VERSION, 5, black)
    bitmap_text(width - margin - 410, 225, "TOP", 16, black)
    arrow_up(width - margin - 250, 350, 16, black)

    cb_x, cb_y, cell = margin + 40, 450, 60
    for row in range(10):
        for col in range(10):
            if (row + col) % 2 == 0:
                rect(cb_x + col * cell, cb_y + row * cell, cb_x + (col + 1) * cell, cb_y + (row + 1) * cell, black, -1)
    rect(cb_x, cb_y, cb_x + 10 * cell, cb_y + 10 * cell, black, 4)

    lx, ly = 980, 460
    for i, thick in enumerate([1, 2, 3, 5, 8, 12]):
        hline(lx, lx + 520, ly + i * 70, black, thick)
    for i in range(24):
        vline(lx + i * 18, ly + 470, ly + 720, black, 2)

    # Slanted edge approximation with stepped rows.
    sx, sy = 1650, 480
    for dy in range(520):
        offset = dy // 7
        hline(sx + offset, sx + 560, sy + dy, black, 1)
    rect(sx - 5, sy - 5, sx + 565, sy + 525, black, 4)

    gx, gy, sw, sh = margin + 40, 1370, 180, 150
    for i in range(11):
        value = int(255 * i / 10)
        rect(gx + i * sw, gy, gx + (i + 1) * sw, gy + sh, (value, value, value), -1)
        rect(gx + i * sw, gy, gx + (i + 1) * sw, gy + sh, black, 2)

    colors = [(220, 30, 30), (30, 170, 70), (40, 80, 220), (245, 220, 35), (30, 200, 210), (210, 40, 190)]
    cx, cy = margin + 40, 1670
    for i, color in enumerate(colors):
        x = cx + i * 330
        rect(x, cy, x + 250, cy + 180, color, -1)
        rect(x, cy, x + 250, cy + 180, black, 4)
    rect(cx, cy + 310, cx + 500, cy + 610, black, -1)
    rect(cx + 560, cy + 310, cx + 1060, cy + 610, (255, 255, 255), -1)
    rect(cx + 560, cy + 310, cx + 1060, cy + 610, black, 4)
    rect(cx + 1120, cy + 310, cx + 1780, cy + 610, (20, 20, 20), -1)
    rect(cx + 1120, cy + 310, cx + 1780, cy + 610, black, 4)

    tx, ty = margin + 40, 2450
    for i, thick in enumerate([2, 3, 4, 6]):
        for j in range(10):
            hline(tx + j * 120, tx + j * 120 + 70, ty + i * 120 + j % 3 * 18, black, thick)

    px, py = 1420, 2390
    for i in range(26):
        hline(px, px + 720, py + i * 16, black, 1)
    for i in range(46):
        vline(px + i * 16, py, py + 400, black, 1)
    rect(px, py, px + 720, py + 400, black, 3)

    _write_rgb_png(path, width, height, pixels)
    return path


def generate_calibration_target_pdf(output_pdf: str) -> Path:
    path = Path(output_pdf)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image
    except Exception as exc:
        raise RuntimeError("PDF output requires Pillow; PNG generation does not") from exc
    tmp_png = path.with_suffix(".png")
    generate_calibration_target_png(str(tmp_png))
    with Image.open(tmp_png) as image:
        image.save(path, "PDF", resolution=300.0)
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate TarotVision printable A4 300 DPI calibration target.",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_PNG,
        help=f"PNG output path. Default: {DEFAULT_OUTPUT_PNG}. Output size: 2480x3508 px.",
    )
    parser.add_argument(
        "--output-pdf",
        help="Optional PDF output path. Requires Pillow; PNG generation still succeeds without it.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output:
        print(f"Wrote PNG target: {generate_calibration_target_png(args.output)}")
    if args.output_pdf:
        try:
            print(f"Wrote PDF target: {generate_calibration_target_pdf(args.output_pdf)}")
        except RuntimeError as exc:
            print(f"Skipped PDF target: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
