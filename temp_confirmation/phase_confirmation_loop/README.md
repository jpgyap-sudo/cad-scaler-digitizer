# CAD Scaler Digitizer — Furniture Confirmation Loop Pack

Drop this pack into your `cad-scaler-digitizer` backend to add the missing workflow:

**AI describes → app proposes template → user confirms/corrects → code generates preview + DXF**

This pack is intentionally MVP/simple. It does not require custom machine learning.

## What this adds

- Vision analysis prompt and parser
- Furniture analysis JSON schema
- Template matcher
- Confirmation/correction model
- SVG preview generator
- DXF generator using `ezdxf`
- Example Melina oval pedestal coffee table template
- CLI demo
- FastAPI route examples

## Install

```bash
pip install -r requirements.txt
```

Optional cloud vision providers:

```bash
export OPENAI_API_KEY=your_key
# or
export GEMINI_API_KEY=your_key
```

## Demo without API

```bash
python demo_confirmation_loop.py
```

This uses the included Melina sample JSON and generates:

```text
outputs/melina_preview.svg
outputs/melina_template.dxf
outputs/melina_approved.json
```

## Integration flow

```text
/upload-image
  -> vision_service.analyze_image()
  -> template_matcher.match_template()
  -> return proposed template + uncertain questions

/user-confirm
  -> correction_engine.apply_corrections()
  -> preview_generator.generate_svg_preview()
  -> dxf_generator.generate_dxf()
```

## Core rule

Do not let AI directly draw the DXF.
AI should only produce structured JSON. The deterministic generator creates DXF.
