import httpx, sys, os
r = httpx.post(
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
    params={"key": os.environ["GEMINI_API_KEY"]},
    json={"contents": [{"parts": [{"text": "Say hello in one word"}]}]},
    timeout=30)
d = r.json()
print(f"Status: {r.status_code}")
print(f"Response: {d.get('candidates',[{}])[0].get('content',{}).get('parts',[{}])[0].get('text','NONE')}")
