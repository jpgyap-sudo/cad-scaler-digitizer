"""End-to-end test of /api/digitize with a generated fixture image."""
import urllib.request, json
from pathlib import Path

img_path = Path('fixtures/round_table/reference.jpg')
boundary = '----TestBoundary'
body = bytearray()

# Build multipart form data
body.extend(f'--{boundary}\r\n'.encode())
body.extend(b'Content-Disposition: form-data; name="file"; filename="test_round.jpg"\r\n')
body.extend(b'Content-Type: image/jpeg\r\n\r\n')
body.extend(img_path.read_bytes())
body.extend(f'\r\n--{boundary}\r\n'.encode())
body.extend(b'Content-Disposition: form-data; name="furniture_type"\r\n\r\n')
body.extend(b'round_pedestal_table\r\n')
body.extend(f'--{boundary}--\r\n'.encode())

req = urllib.request.Request(
    'http://localhost:5001/api/digitize',
    data=bytes(body),
    headers={'Content-Type': f'multipart/form-data; boundary={boundary}'}
)

try:
    r = urllib.request.urlopen(req, timeout=60)
    data = json.loads(r.read())
    print(f"Job ID: {data.get('job_id','?')[:20]}...")
    print(f"DXF file: {data.get('dxf_file','?')}")
    print(f"SVG preview: {'YES' if data.get('preview_svg') else 'NO'}")
    print(f"Furniture: {data.get('furniture',{}).get('type','?')}")
    print(f"Confidence: {data.get('furniture',{}).get('confidence',0)}")
    dims = data.get('detected',{}).get('dimensions',[])
    print(f"Dimensions found: {len(dims)}")
    for d in dims[:5]:
        print(f"  {d.get('tag','?')}: {d.get('value_cm','?')}cm")
    warns = data.get('warnings',[])
    if warns: print(f"Warnings: {warns}")
    acc = data.get('accuracy_pipeline',{})
    assoc = acc.get('associations',{})
    print(f"Associations: {len(assoc.get('associations',[]))} pairs")
    sc = acc.get('scale')
    if sc:
        print(f"Scale: px_per_cm={sc.get('x_scale',{}).get('px_per_cm','?')}")
    schema = data.get('component_schema')
    if schema:
        sections = [s['name'] for s in schema]
        print(f"Component schema: {', '.join(sections)}")
    print()
    print("DIGITIZE ENDPOINT: OK")
except urllib.error.HTTPError as e:
    body = e.read().decode()[:500]
    print(f"HTTP {e.code}: {body}")
except Exception as e:
    import traceback
    print(f"Error: {e}")
    traceback.print_exc()
