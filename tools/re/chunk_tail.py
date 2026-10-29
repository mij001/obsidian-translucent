import re, os, sys, json, collections
src, out, target = sys.argv[1], sys.argv[2], int(sys.argv[3])
lines = open(src, encoding='utf8').read().split('\n')
# runtime header ends at the first "(() => {" at indent 2; chunk the body after it
body_start = next(i for i, l in enumerate(lines) if l.startswith('  }(), n.o = ') or l.startswith('  }, (() => {'))
start_pat = re.compile(r'^    (class |function |var |let |const |async function )')
bounds = [body_start]
last = body_start
for i in range(body_start + 1, len(lines)):
    if i - last >= target and start_pat.match(lines[i]) and lines[i - 1].rstrip().endswith(('}', ';', '},')):
        bounds.append(i); last = i
bounds.append(len(lines))
anchors = {
 'codemirror-editor': r'cm-editor|cm-line|EditorView|EditorState|@codemirror',
 'lezer-markdown-parse': r'lezer|NodeType|TreeCursor|parser\.',
 'workspace-leaves': r'workspace-leaf|workspace-split|workspace-tabs|WorkspaceLeaf|getLeaf',
 'vault-files': r'TFile|TFolder|vault\.|adapter\.|getAbstractFileByPath',
 'metadata-cache': r'metadataCache|frontmatter|resolvedLinks|unresolvedLinks',
 'markdown-render': r'markdown-preview|markdown-rendered|MarkdownRenderer|postProcessor',
 'plugins-api': r'registerView|addCommand|loadData|manifest\.json|community-plugins',
 'themes-css': r'cssTheme|enabledCssSnippets|theme\.css|snippets',
 'canvas': r'canvas-node|canvas-edge|\.canvas',
 'graph-view': r'graph-view|forceLink|d3-force|graph\.json',
 'bases': r'\.base\b|bases-|BaseView',
 'properties-yaml': r'metadata-properties|yaml|property-widget',
 'sync-publish': r'obsidian\.md/|sync-|publish-|syncing',
 'search': r'global-search|search-result|matchesQuery|searchQuery',
 'ui-modals-menus': r'modal-container|\.Menu\(|suggestion-container|setting-item|Setting\(',
 'electron-ipc': r'ipcRenderer|electron|remote\.|BrowserWindow',
 'i18n': r'getLanguage|i18n|lang\b',
 'importer-web': r'webview|defuddle|web-viewer|webviewer',
 'daily-bookmarks-templates': r'daily-notes|bookmarks|templates',
}
os.makedirs(out, exist_ok=True)
toc = []
for n in range(len(bounds) - 1):
    a, b = bounds[n], bounds[n + 1]
    text = '\n'.join(lines[a:b])
    score = collections.Counter({k: len(re.findall(p, text)) for k, p in anchors.items()})
    top = [k for k, v in score.most_common(3) if v >= 5]
    name = f'{n:03d}_' + ('_'.join(t.split('-')[0] for t in top[:2]) if top else 'misc')
    open(f'{out}/{name}.js', 'w', encoding='utf8').write(text + '\n')
    toc.append({'file': name + '.js', 'lines': f'{a+1}-{b}', 'count': b - a, 'top': dict((k, v) for k, v in score.most_common(4) if v)})
json.dump(toc, open(f'{out}/_toc.json', 'w'), indent=1)
print(len(toc), 'chunks')
for t in toc: print(t['file'], t['lines'], t['top'])
