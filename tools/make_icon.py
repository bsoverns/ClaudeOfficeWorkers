"""Draws office.ico (Claude's orange starburst) at the repo root, standard library only. Run by scripts/build.bat.
With --icns it draws office.icns for the Mac app instead (run by scripts/build_mac.sh).
With --cursor it draws cursor_office.ico / .icns: the Cursor office's cube and pointer, as on its page (CUBE_SVG in index.html)."""
import math
import os
import struct
import sys
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # tools/.. = the repo root
COLOR = (0xD9, 0x77, 0x57)
CUBE = (   # (color, points), last on top, in the 64x64 frame centred on 0,0
    ((0x4B, 0x51, 0x5C), ((0, -30), (26, -15), (0, 0), (-26, -15))),
    ((0x2A, 0x2E, 0x35), ((-26, -15), (0, 0), (0, 30), (-26, 15))),
    ((0x17, 0x19, 0x1D), ((26, -15), (26, 15), (0, 30), (0, 0))),
    ((0xF4, 0xF5, 0xF7), ((-11, -12), (13, -1), (2, 2), (-1, 14))),
)


def inside(x: float, y: float) -> bool:
    """Point in the 64x64 starburst centred on 0,0: 12 rounded rays plus a centre disc."""
    if x * x + y * y <= 13 * 13:
        return True
    for i in range(12):
        a = math.radians(i * 30)
        rx = x * math.cos(a) + y * math.sin(a)          # rotate the point into the ray's frame
        ry = -x * math.sin(a) + y * math.cos(a)
        cy = min(-4.0, max(-26.0, ry))                  # nearest point on the ray's spine
        if rx * rx + (ry - cy) ** 2 <= 16:
            return True
    return False


def in_polygon(x: float, y: float, pts: tuple) -> bool:
    hit = False
    for (ax, ay), (bx, by) in zip(pts, pts[1:] + pts[:1]):
        if (ay > y) != (by > y) and x < ax + (y - ay) * (bx - ax) / (by - ay):
            hit = not hit
    return hit


def starburst(x: float, y: float) -> tuple | None:
    return COLOR if inside(x, y) else None


def cube(x: float, y: float) -> tuple | None:
    return next((c for c, pts in reversed(CUBE) if in_polygon(x, y, pts)), None)


def png(size: int, paint=starburst) -> bytes:
    ss = 3
    rows = []
    for py in range(size):
        row = bytearray([0])
        for px in range(size):
            hits = [c for c in (paint((px + (i + 0.5) / ss) / size * 64 - 32, (py + (j + 0.5) / ss) / size * 64 - 32)
                                for i in range(ss) for j in range(ss)) if c]
            rgb = [round(sum(c[k] for c in hits) / len(hits)) for k in range(3)] if hits else [0, 0, 0]
            row += bytes(rgb) + bytes([round(255 * len(hits) / (ss * ss))])
        rows.append(bytes(row))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + chunk(b"IEND", b""))


def icns(name: str, paint) -> None:
    """The Mac icon: PNGs at 128, 256 and 512 px in an .icns container."""
    body = b""
    for kind, size in ((b"ic07", 128), (b"ic08", 256), (b"ic09", 512)):
        img = png(size, paint)
        body += kind + struct.pack(">I", len(img) + 8) + img
    with open(os.path.join(ROOT, name + ".icns"), "wb") as f:
        f.write(b"icns" + struct.pack(">I", len(body) + 8) + body)
    print(f"wrote {name}.icns")


def main() -> None:
    name, paint = ("cursor_office", cube) if "--cursor" in sys.argv[1:] else ("office", starburst)
    if "--icns" in sys.argv[1:]:
        icns(name, paint)
        return
    sizes = [16, 32, 48, 256]
    images = [png(s, paint) for s in sizes]
    out = struct.pack("<HHH", 0, 1, len(sizes))
    offset = 6 + 16 * len(sizes)
    for s, img in zip(sizes, images):
        out += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(img), offset)
        offset += len(img)
    with open(os.path.join(ROOT, name + ".ico"), "wb") as f:
        f.write(out + b"".join(images))
    print(f"wrote {name}.ico")


if __name__ == "__main__":
    main()
