// Entry point of the "Obsidian Translucent" app (generated copy lives in the build directory).
// It does two things, then hands over to the unmodified Obsidian launcher (app.asar):
//   1. injects the translucent CSS into every Obsidian window, so no vault or settings file is touched;
//   2. gives windows our own icon.
// Settings (optional) live in <user-data-dir>/translucent.json: {"alpha": 0.4, "radius": 10}
const { app, nativeImage } = require('electron');
const fs = require('fs');
const path = require('path');

const baseCss = fs.readFileSync(path.join(__dirname, 'translucent.css'), 'utf8');

function settingsCss() {
  let cfg = {};
  try {
    cfg = JSON.parse(fs.readFileSync(path.join(app.getPath('userData'), 'translucent.json'), 'utf8'));
  } catch (e) { /* no settings file: defaults from the CSS */ }
  const vars = [];
  if (typeof cfg.alpha === 'number') vars.push(`--tl-alpha: ${cfg.alpha}`);
  if (typeof cfg.radius === 'number') vars.push(`--tl-radius: ${cfg.radius}px`);
  if (typeof cfg.clipRight === 'number') vars.push(`--tl-clip-right: ${cfg.clipRight}px`);
  if (typeof cfg.clipBottom === 'number') vars.push(`--tl-clip-bottom: ${cfg.clipBottom}px`);
  return vars.length ? `\nbody { ${vars.join('; ')}; }\n` : '';
}

const icon = nativeImage.createFromPath(path.join(__dirname, 'icon.png'));

app.on('web-contents-created', (_event, contents) => {
  if (contents.getType() !== 'window') return; // not <webview> or devtools
  contents.on('dom-ready', () => {
    const url = contents.getURL();
    if (/starter\.html|help\.html/.test(url)) return; // vault picker and help keep their normal look
    contents.insertCSS(baseCss + settingsCss()).catch(() => {});
  });
});

app.on('browser-window-created', (_event, win) => {
  if (!icon.isEmpty()) win.setIcon(icon);
});

require(path.join(__dirname, 'app.asar', 'main.js'));
