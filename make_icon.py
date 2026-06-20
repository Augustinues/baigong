"""生成 baigong.icns 图标"""
import struct, zlib, os, subprocess

def create_png(width, height, pixels):
    def chunk(chunk_type, data):
        c = chunk_type + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
    sig = b'\x89PNG\r\n\x1a\n'
    ihdr = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    raw = b''
    for y in range(height):
        raw += b'\x00'
        for x in range(width):
            idx = (y * width + x) * 4
            raw += bytes(pixels[idx:idx+4])
    compressed = zlib.compress(raw)
    return sig + chunk(b'IHDR', ihdr) + chunk(b'IDAT', compressed) + chunk(b'IEND', b'')

w, h = 256, 256
pixels = bytearray()
cx, cy = w // 2, h // 2
for y in range(h):
    for x in range(w):
        dx_center = abs(x - cx)
        dy_center = abs(y - cy)
        corner_r = 48
        in_shape = True
        if dx_center > cx - corner_r and dy_center > cy - corner_r:
            cd = ((dx_center - (cx - corner_r))**2 + (dy_center - (cy - corner_r))**2)**0.5
            if cd > corner_r:
                in_shape = False
        if in_shape:
            dist = ((x - cx)**2 + (y - cy)**2)**0.5 / cx
            if dist < 0.25:
                pixels.extend([255, 255, 255, 230])
            else:
                px = 79 + int(dist * 20)
                py = 91 + int(dist * 20)
                pixels.extend([min(px, 255), min(py, 255), 245, 240])
        else:
            pixels.extend([0, 0, 0, 0])

png_data = create_png(w, h, pixels)
os.makedirs('baigong.iconset', exist_ok=True)
with open('baigong_256.png', 'wb') as f:
    f.write(png_data)

# Use sips to resize
for s in [16, 32, 64, 128, 256]:
    subprocess.run(['sips', '-z', str(s), str(s), 'baigong_256.png',
                    '--out', f'baigong.iconset/icon_{s}x{s}.png'], check=True, capture_output=True)
    subprocess.run(['sips', '-z', str(s), str(s), 'baigong_256.png',
                    '--out', f'baigong.iconset/icon_{s}x{s}@2x.png'], check=True, capture_output=True)

subprocess.run(['iconutil', '-c', 'icns', 'baigong.iconset', '-o', 'baigong.icns'], check=True)
print('ICNS created!')
os.unlink('baigong_256.png')
