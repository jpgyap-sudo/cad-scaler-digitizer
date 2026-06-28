import json, os

batches = {}
for b in [1,2,3,4,5,6]:
    d = f'temp_batch{b}'
    if not os.path.isdir(d):
        continue
    templates = []
    for root, dirs, files in os.walk(d):
        for f in files:
            if not f.endswith('.json'): continue
            if f.startswith('catalog_index') or f.startswith('index') or f.startswith('visual_dna') or f.startswith('READ') or f.startswith('INTEGRATION'):
                continue
            path = os.path.join(root, f)
            try:
                t = json.load(open(path, encoding='utf-8'))
                family = t.get('template_family', t.get('product_type', 'unknown'))
                title = t.get('title', t.get('product_title', f))
                components = t.get('components', t.get('tags', []))
                views = t.get('views_required', [])
                templates.append({'file': f, 'family': family, 'title': title, 'components': components[:5], 'views': views})
            except:
                pass
    batches[b] = templates
    print(f'Batch {b}: {len(templates)} valid templates')

for b, templates in batches.items():
    families = {}
    for t in templates:
        f = t['family']
        families[f] = families.get(f, 0) + 1
    print(f'\nBatch {b} families:')
    for fam, count in sorted(families.items(), key=lambda x: -x[1])[:10]:
        print(f'  {fam}: {count}')
