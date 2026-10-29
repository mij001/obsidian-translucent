import sys, os, jsbeautifier
opts = jsbeautifier.default_options(); opts.indent_size = 2; opts.wrap_line_length = 0; opts.preserve_newlines = False
src, dst = sys.argv[1], sys.argv[2]
for f in sys.argv[3:]:
    s = open(os.path.join(src, f), encoding='utf8').read()
    out = jsbeautifier.beautify(s, opts)
    os.makedirs(os.path.dirname(os.path.join(dst, f)) or dst, exist_ok=True)
    open(os.path.join(dst, f), 'w', encoding='utf8').write(out)
    print(f, len(s), '->', len(out), out.count('\n'), 'lines', flush=True)
