from app.backend.product_classifier import classify_product

r = classify_product("sofa", ["rectangle"], ["seat"])
print(f"Family: {r['family']} conf={r['family_confidence']} matches={len(r['matches'])}")
for m in r['matches'][:3]:
    print(f"  {m['family']} score={m['score']}")
