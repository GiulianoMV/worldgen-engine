"""Shared standard-library RGB PNG writer."""
import struct
import zlib


def chunk(kind, data):
    return (struct.pack('!I', len(data)) + kind + data
            + struct.pack('!I', zlib.crc32(kind + data) & 0xffffffff))


def write_png(path, pixels, width, height, description):
    if len(pixels) != width * height * 3:
        raise ValueError('RGB buffer does not match image dimensions.')
    stride = width * 3
    scanlines = bytearray()
    for y in range(height):
        scanlines.append(0)
        scanlines.extend(pixels[y * stride:(y + 1) * stride])
    png = (b'\x89PNG\r\n\x1a\n'
           + chunk(b'IHDR', struct.pack('!2I5B', width, height, 8, 2, 0, 0, 0))
           + chunk(b'tEXt', b'Description\x00' + description.encode('latin-1', errors='replace'))
           + chunk(b'IDAT', zlib.compress(scanlines))
           + chunk(b'IEND', b''))
    with path.open('xb') as output:
        output.write(png)
