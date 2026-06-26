"""Test rectangular table digitize (BUG-7: SVG type-aware)."""
import urllib.request, json
from pathlib import Path

img_path = Path('fixtures/rectangular_table/reference.jpg')
boundary = '----TestBoundary'
body = bytearray()
body.extend(f'--{boundary}\r\n'.encode())
body.extend(b'Content-Disposition: form-data; name="file"; filename="test_rect.jpg"\r\n')
body.extend(b'Content-Type: image/jpeg\r\n\r\n')
body.extend(img_path.read_bytes())
body.extend(f'\r\n--{boundary}\r\n'.encode())
body.extend(b'Content-Disposition: form-data; name="furniture_type"\r\n\r\n')
body.extend(b'rectangular_table\r\n')
body.extend(f'--{boundary}--\r\n'.encode())

req = urllib.request.Request(
    'http://localhost:5001/api/digitize',
    data=bytes(body),
    headers={'Content-Type': f'multipart/form-data; boundary={boundary}'}
)
r = urllib.request.urlopen(req, timeout=60)
data = json.loads(r.read())
print(f"Furniture: {data.get('furniture',{}).get('type','?')}")
print(f"SVG preview: {'YES' if data.get('preview_svg') else 'NO'}")
print(f"DXF file: {data.get('dxf_file','?')}")
dims = data.get('resolved_dimensions', {})
if dims:
    for k, v in dims.items():
        print(f"  resolved: {k} = {v}")
else:
    print("  (no resolved dimensions)")
print("OK" if data.get('preview_svg') else "SVG FAILED")
