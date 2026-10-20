"""Draws office.ico (Claude's orange starburst) at the repo root, standard library only. Run by scripts/build.bat.
With --icns it draws office.icns for the Mac app instead (run by scripts/build_mac.sh)."""
import math
import os
import struct
import sys
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # tools/.. = the repo root
COLOR = (0xD9, 0x77, 0x57)


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


def png(size: int) -> bytes:
    ss = 3
    rows = []
    for py in range(size):
        row = bytearray([0])
        for px in range(size):
            hits = sum(inside((px + (i + 0.5) / ss) / size * 64 - 32, (py + (j + 0.5) / ss) / size * 64 - 32)
                       for i in range(ss) for j in range(ss))
            row += bytes(COLOR) + bytes([round(255 * hits / (ss * ss))])
        rows.append(bytes(row))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + chunk(b"IEND", b""))


def icns() -> None:
    """The Mac icon: PNGs at 128, 256 and 512 px in an .icns container."""
    body = b""
    for kind, size in ((b"ic07", 128), (b"ic08", 256), (b"ic09", 512)):
        img = png(size)
        body += kind + struct.pack(">I", len(img) + 8) + img
    with open(os.path.join(ROOT, "office.icns"), "wb") as f:
        f.write(b"icns" + struct.pack(">I", len(body) + 8) + body)
    print("wrote office.icns")


def main() -> None:
    if "--icns" in sys.argv[1:]:
        icns()
        return
    sizes = [16, 32, 48, 256]
    images = [png(s) for s in sizes]
    out = struct.pack("<HHH", 0, 1, len(sizes))
    offset = 6 + 16 * len(sizes)
    for s, img in zip(sizes, images):
        out += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(img), offset)
        offset += len(img)
    with open(os.path.join(ROOT, "office.ico"), "wb") as f:
        f.write(out + b"".join(images))
    print("wrote office.ico")


if __name__ == "__main__":
    main()
