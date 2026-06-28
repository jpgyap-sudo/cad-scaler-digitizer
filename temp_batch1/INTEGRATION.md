# Integration

Copy `templates/*.json` into:

`resources/homeu_product_templates/`

Then update your app to load both:

- `resources/furniture_templates/`
- `resources/homeu_product_templates/`

Recommended pipeline:

1. Shopify product image or uploaded image
2. Vision API returns furniture_analysis.json
3. Template matcher chooses closest HomeU template
4. App shows confirmation UI
5. User corrects wrong assumptions
6. App generates SVG/PNG preview
7. User approves
8. DXF generator runs from approved JSON

Do not use PNG/JPEG as the CAD source. Use it as reference only.
