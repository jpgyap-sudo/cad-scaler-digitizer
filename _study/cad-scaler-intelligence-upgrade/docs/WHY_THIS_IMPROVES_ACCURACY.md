# Why This Improves Accuracy

Old pipeline:

```txt
OCR + template guesses → DXF
```

New pipeline:

```txt
pixels → geometry
OCR → dimensions
dimensions → geometry association
scale solver → mm conversion
confidence → validation
```

Correct priority:

```txt
1. User-confirmed geometry
2. OCR-associated geometry
3. Pixel-detected geometry
4. Reference-library estimated geometry
5. Template default
```

Template default should always be low confidence.
