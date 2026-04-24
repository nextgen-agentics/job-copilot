"""
create_icons.py — Generates PNG icons for the Chrome extension.
Runs standalone with zero dependencies (pure Python stdlib).
Creates: icons/icon16.png, icons/icon48.png, icons/icon128.png

Usage:
    python3 create_icons.py
"""
import struct
import zlib
import math
import os


def _make_png_bytes(size: int) -> bytes:
    """
    Create a purple target/crosshair icon on a dark background.
    Pure Python — uses only struct and zlib from stdlib.
    """
    cx, cy = size / 2.0, size / 2.0
    r_outer = size * 0.42
    r_mid   = size * 0.28
    r_inner = size * 0.14
    ring_w  = max(1.0, size * 0.055)
    cross_w = max(1, int(size * 0.045))

    # Colours
    BG  = (0x0d, 0x11, 0x17)      # dark navy
    PUR = (0x8b, 0x5c, 0xf6)      # purple #8b5cf6
    WHT = (0xff, 0xff, 0xff)       # white dot centres

    raw_rows = []
    for y in range(size):
        row = bytearray([0x00])    # PNG filter byte: None
        for x in range(size):
            dx = x - cx
            dy = y - cy
            dist = math.sqrt(dx * dx + dy * dy)

            # Outside canvas → background
            r, g, b = BG

            # Rings
            on_ring = (
                abs(dist - r_outer) < ring_w or
                abs(dist - r_mid)   < ring_w or
                abs(dist - r_inner) < ring_w
            )

            # Cross-hair lines (only inside outer ring)
            on_cross = (
                dist < r_outer + ring_w / 2 and
                (abs(dx) < cross_w or abs(dy) < cross_w)
            )

            # White dots at ring-crosshair intersections
            on_dot = False
            for ring_r in (r_outer, r_mid):
                for angle in (0, math.pi / 2, math.pi, 3 * math.pi / 2):
                    ddx = x - (cx + ring_r * math.cos(angle))
                    ddy = y - (cy + ring_r * math.sin(angle))
                    if math.sqrt(ddx * ddx + ddy * ddy) < max(1.5, size * 0.028):
                        on_dot = True

            if on_dot:
                r, g, b = WHT
            elif on_ring or on_cross:
                r, g, b = PUR

            row += bytes([r, g, b])
        raw_rows.append(bytes(row))

    raw_data = b"".join(raw_rows)

    def _chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = _chunk(
        b"IHDR",
        struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0),
    )
    idat = _chunk(b"IDAT", zlib.compress(raw_data, 9))
    iend = _chunk(b"IEND", b"")

    return signature + ihdr + idat + iend


def create_icons(base_dir: str = ".") -> None:
    icons_dir = os.path.join(base_dir, "icons")
    os.makedirs(icons_dir, exist_ok=True)

    for size in (16, 48, 128):
        path = os.path.join(icons_dir, f"icon{size}.png")
        png = _make_png_bytes(size)
        with open(path, "wb") as f:
            f.write(png)
        print(f"  ✓ Created {path} ({len(png)} bytes)")


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    print("Generating JobCopilot AI extension icons...")
    create_icons(script_dir)
    print("Done! Icons saved to extension/icons/")
