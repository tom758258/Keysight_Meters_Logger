from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = REPO_ROOT / "src" / "meters_tool_webui" / "static"
NODE = shutil.which("node")


def test_theme_control_and_initial_render_bootstrap_are_present():
    index = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    assert 'id="theme-toggle"' in index
    assert 'id="theme-toggle-label"' in index
    assert 'data-i18n="theme.system"' in index
    assert 'aria-hidden="true"' in index
    assert index.index("meters-tool.webui.theme") < index.index("/static/styles.css")


@pytest.mark.skipif(NODE is None, reason="Node.js is required for theme runtime tests")
def test_theme_preference_runtime_behavior():
    script = r'''
import assert from "node:assert/strict";

const [themeUrl, i18nUrl] = process.argv.slice(1);
const theme = await import(themeUrl);
const i18n = await import(i18nUrl);

class FakeElement {
  constructor() {
    this.attributes = {};
    this.dataset = {};
    this.listeners = new Map();
    this.textContent = "";
  }
  addEventListener(name, listener) { this.listeners.set(name, listener); }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  click() { this.listeners.get("click")?.(); }
}

class Storage {
  constructor(value = null, readFails = false, writeFails = false) {
    this.value = value;
    this.readFails = readFails;
    this.writeFails = writeFails;
    this.writes = [];
  }
  getItem(key) {
    assert.equal(key, "meters-tool.webui.theme");
    if (this.readFails) throw new Error("read failed");
    return this.value;
  }
  setItem(key, value) {
    if (this.writeFails) throw new Error("write failed");
    this.writes.push([key, value]);
    this.value = value;
  }
}

class MediaQuery {
  constructor(matches) { this.matches = matches; this.listener = null; }
  addEventListener(name, listener) {
    assert.equal(name, "change");
    this.listener = listener;
  }
  change(matches) { this.matches = matches; this.listener?.({ matches }); }
}

assert.deepEqual(theme.SUPPORTED_THEME_PREFERENCES, ["system", "light", "dark"]);
for (const preference of theme.SUPPORTED_THEME_PREFERENCES) {
  assert.equal(theme.isSupportedThemePreference(preference), true);
}
assert.equal(theme.isSupportedThemePreference("contrast"), false);
assert.equal(theme.nextThemePreference("system"), "light");
assert.equal(theme.nextThemePreference("light"), "dark");
assert.equal(theme.nextThemePreference("dark"), "system");
assert.equal(theme.readSavedThemePreference(new Storage("contrast")), null);
assert.equal(theme.readSavedThemePreference(new Storage(null, true)), null);
assert.equal(theme.persistThemePreference(new Storage(null, false, true), "dark"), false);
assert.equal(theme.effectiveTheme("system", new MediaQuery(false)), "light");
assert.equal(theme.effectiveTheme("system", new MediaQuery(true)), "dark");
assert.equal(theme.effectiveTheme("light", new MediaQuery(true)), "light");
assert.equal(theme.effectiveTheme("dark", new MediaQuery(false)), "dark");

const button = new FakeElement();
const label = new FakeElement();
const documentElement = new FakeElement();
const storage = new Storage("dark");
const media = new MediaQuery(false);
const ui = theme.initializeThemeUi({ button, label, documentElement, storage, mediaQuery: media });

assert.equal(ui.getPreference(), "dark");
assert.equal(documentElement.dataset.theme, "dark");
assert.equal(label.textContent, "Dark");
assert.equal(button.attributes["aria-label"], "Switch theme to System");
media.change(true);
assert.equal(documentElement.dataset.theme, "dark");

button.click();
assert.equal(ui.getPreference(), "system");
assert.equal(documentElement.dataset.theme, "dark");
assert.deepEqual(storage.writes.at(-1), ["meters-tool.webui.theme", "system"]);
media.change(false);
assert.equal(documentElement.dataset.theme, "light");

button.click();
assert.equal(ui.getPreference(), "light");
media.change(true);
assert.equal(documentElement.dataset.theme, "light");
button.click();
assert.equal(ui.getPreference(), "dark");

i18n.setLocale("zh-TW");
ui.refresh();
assert.equal(label.textContent, "深色");
assert.equal(button.attributes.title, "切換主題至系統");

const fallbackDocument = new FakeElement();
const fallbackUi = theme.initializeThemeUi({
  button: new FakeElement(),
  label: new FakeElement(),
  documentElement: fallbackDocument,
  storage: new Storage("invalid"),
  mediaQuery: new MediaQuery(true),
});
assert.equal(fallbackUi.getPreference(), "system");
assert.equal(fallbackDocument.dataset.theme, "dark");

process.stdout.write(JSON.stringify({ ok: true }));
'''
    completed = subprocess.run(
        [
            NODE,
            "--input-type=module",
            "--eval",
            script,
            (STATIC_DIR / "theme_ui.js").resolve().as_uri(),
            (STATIC_DIR / "i18n.js").resolve().as_uri(),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert completed.returncode == 0, (
        "Node theme preference contract failed\n"
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )
    assert completed.stdout == '{"ok":true}'
