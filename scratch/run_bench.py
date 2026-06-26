import urllib.request, json, sys

r = urllib.request.urlopen('http://localhost:5001/api/benchmark', timeout=300)
data = json.loads(r.read())

if 'error' in data:
    print('ERROR:', data['error'])
    sys.exit(1)

fixtures = data.get('fixtures', [])
for f in fixtures:
    score = f.get('overall_score', 0)
    name = f.get('name', '?')
    dim_acc = f.get('dimension_accuracy_pct', 0)
    assoc = f.get('association_count', 0)
    match = 'MATCH' if f.get('furniture_type_match') else 'MISS'
    status = 'PASS' if score >= 60 else 'FAIL'
    dims = f.get('dimension_accuracies', [])
    dim_detail = ' | '.join(f"{d['tag']}={d['error_pct']:.0f}%" for d in dims[:4])
    print(f'{status:4s} | {name:30s} | {match:4s} | score={score:5.1f} | dim={dim_acc:5.1f}% | {dim_detail}')

avg = data.get('average_score', 0)
passed = data.get('passed_fixtures', 0)
total = data.get('total_fixtures', 0)
dim_err = data.get('dimension_error_avg', 0)
print(f'\nSummary: {passed}/{total} passed | avg_score={avg:.0f}% | avg_dim_err={dim_err:.1f}%')
