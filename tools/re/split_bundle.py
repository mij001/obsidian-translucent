import re, os, sys, json
src = sys.argv[1]; out = sys.argv[2]
lines = open(src, encoding='utf8').read().split('\n')
pat = re.compile(r'^      (\d+): (?:\(|function)')
starts = [(i, int(pat.match(l).group(1))) for i, l in enumerate(lines) if pat.match(l)]
# the module map closes at the first line at indent 4 that is "}," or "}" after the last start
last = starts[-1][0]
end = next(i for i in range(last + 1, len(lines)) if re.match(r'^    \}[,;]?$', lines[i]))
os.makedirs(out + '/modules', exist_ok=True)
index = []
for n, (i, mid) in enumerate(starts):
    j = starts[n + 1][0] if n + 1 < len(starts) else end
    body = '\n'.join(lines[i:j]).rstrip().rstrip(',')
    open(f'{out}/modules/{mid}.js', 'w', encoding='utf8').write(body + '\n')
    reqs = sorted(set(int(x) for x in re.findall(r'\bn\((\d+)\)', body)))
    index.append({'id': mid, 'lines': j - i, 'bytes': len(body), 'requires': reqs})
open(f'{out}/bootstrap_tail.js', 'w', encoding='utf8').write('\n'.join(lines[end:]) + '\n')
open(f'{out}/bootstrap_head.js', 'w', encoding='utf8').write('\n'.join(lines[:starts[0][0]]) + '\n')
json.dump(index, open(f'{out}/index.json', 'w'))
print(len(starts), 'modules; map ends at line', end, 'of', len(lines), '; tail lines', len(lines) - end)
