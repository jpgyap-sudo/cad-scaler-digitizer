"""Basic API endpoint health tests. Run: python test-api-endpoints.py"""
import httpx, sys, asyncio

ENDPOINTS = [
    # Python worker
    ("GET", "http://python-worker:8001/health", None, lambda r: r.status_code == 200),
    ("GET", "http://python-worker:8001/api/progress", None, lambda r: r.status_code == 200),
    ("GET", "http://python-worker:8001/api/templates", None, lambda r: r.status_code == 200),
    ("GET", "http://python-worker:8001/api/templates/suggest?furniture_type=table&width_cm=100", None, lambda r: r.status_code == 200),
    # Node API
    ("GET", "http://node-api:4000/health", None, lambda r: r.status_code == 200),
    ("GET", "http://node-api:4000/api/health/redis", None, lambda r: r.status_code == 200),
    # Verify endpoints return expected JSON fields
    ("GET", "http://python-worker:8001/api/templates", None, lambda r: r.json().get("count", 0) >= 18),
    ("POST", "http://python-worker:8001/api/verify", {"product_id":"test","furniture_type":"table","detected_dims":{"width_cm":100}}, lambda r: r.json().get("summary", "").startswith("table")),
]

async def main():
    passed = 0
    failed = 0
    async with httpx.AsyncClient(timeout=15) as c:
        for method, url, body, check in ENDPOINTS:
            try:
                if method == "GET":
                    r = await c.get(url)
                else:
                    r = await c.post(url, json=body)
                ok = check(r)
                status = "PASS" if ok else "FAIL"
                if ok: passed += 1
                else:
                    failed += 1
                    print(f"  {status} {url} — response didn't meet check")
            except Exception as e:
                failed += 1
                print(f"  FAIL {url} — {e}")
    total = passed + failed
    print(f"\n{passed}/{total} tests passed ({passed/total*100:.0f}%)")
    sys.exit(0 if failed == 0 else 1)

asyncio.run(main())
