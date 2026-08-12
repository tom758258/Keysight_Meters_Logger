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
    theme_source = (STATIC_DIR / "theme_ui.js").read_text(encoding="utf-8")

    assert 'id="theme-toggle"' in index
    assert 'id="theme-toggle-label"' in index
    assert 'data-i18n="theme.system"' in index
    assert 'aria-hidden="true"' in index
    assert index.index("document.cookie") < index.index("/static/styles.css")
    assert index.index("meters-tool.webui.theme") < index.index("/static/styles.css")
    assert 'localStorage.getItem("meters-tool.webui.theme")' not in index
    assert "localStorage" not in theme_source


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

class CookieDocument {
  constructor(value = "", readFails = false, writeFails = false) {
    this.value = value;
    this.readFails = readFails;
    this.writeFails = writeFails;
    this.writes = [];
  }
  get cookie() {
    if (this.readFails) throw new Error("read failed");
    return this.value;
  }
  set cookie(value) {
    if (this.writeFails) throw new Error("write failed");
    this.writes.push(value);
    this.value = value.split(";", 1)[0];
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
assert.equal(
  theme.readSavedThemePreference(
    new CookieDocument("other=value; meters-tool.webui.theme=dark; another=value")
  ),
  "dark",
);
assert.equal(theme.readSavedThemePreference(new CookieDocument()), null);
assert.equal(
  theme.readSavedThemePreference(new CookieDocument("meters-tool.webui.theme=contrast")),
  null,
);
assert.equal(theme.readSavedThemePreference(new CookieDocument("", true)), null);
assert.equal(theme.effectiveTheme("system", new MediaQuery(false)), "light");
assert.equal(theme.effectiveTheme("system", new MediaQuery(true)), "dark");
assert.equal(theme.effectiveTheme("light", new MediaQuery(true)), "light");
assert.equal(theme.effectiveTheme("dark", new MediaQuery(false)), "dark");

const button = new FakeElement();
const label = new FakeElement();
const documentElement = new FakeElement();
const cookieDocument = new CookieDocument("meters-tool.webui.theme=dark");
const media = new MediaQuery(false);
const ui = theme.initializeThemeUi({
  button,
  label,
  documentElement,
  cookieDocument,
  mediaQuery: media,
});

assert.equal(ui.getPreference(), "dark");
assert.equal(documentElement.dataset.theme, "dark");
assert.equal(label.textContent, "Dark");
assert.equal(button.attributes["aria-label"], "Switch theme to System");
media.change(true);
assert.equal(documentElement.dataset.theme, "dark");

button.click();
assert.equal(ui.getPreference(), "system");
assert.equal(documentElement.dataset.theme, "dark");
const persistedCookie = cookieDocument.writes.at(-1);
assert.match(persistedCookie, /^meters-tool\.webui\.theme=system;/);
assert.match(persistedCookie, /(?:^|; )Max-Age=([1-9][0-9]*)(?:;|$)/);
assert.match(persistedCookie, /(?:^|; )Path=\/(?:;|$)/);
assert.match(persistedCookie, /(?:^|; )SameSite=Lax(?:;|$)/);
assert.doesNotMatch(persistedCookie, /(?:^|; )Domain=/i);
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
  cookieDocument: new CookieDocument("meters-tool.webui.theme=invalid"),
  mediaQuery: new MediaQuery(true),
});
assert.equal(fallbackUi.getPreference(), "system");
assert.equal(fallbackDocument.dataset.theme, "dark");

const unsavedButton = new FakeElement();
const unsavedDocument = new FakeElement();
const unsavedUi = theme.initializeThemeUi({
  button: unsavedButton,
  label: new FakeElement(),
  documentElement: unsavedDocument,
  cookieDocument: new CookieDocument("", false, true),
  mediaQuery: new MediaQuery(false),
});
unsavedButton.click();
assert.equal(unsavedUi.getPreference(), "light");
assert.equal(unsavedDocument.dataset.theme, "light");

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
