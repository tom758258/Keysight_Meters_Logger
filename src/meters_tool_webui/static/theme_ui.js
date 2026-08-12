import { t } from "./i18n.js";

export const THEME_COOKIE_NAME = "meters-tool.webui.theme";
export const SUPPORTED_THEME_PREFERENCES = Object.freeze(["system", "light", "dark"]);

export function isSupportedThemePreference(value) {
  return SUPPORTED_THEME_PREFERENCES.includes(value);
}

export function readSavedThemePreference(cookieDocument) {
  try {
    const cookie = cookieDocument?.cookie;
    if (typeof cookie !== "string") {
      return null;
    }
    const prefix = `${THEME_COOKIE_NAME}=`;
    const saved = cookie
      .split(";")
      .map((part) => part.trim())
      .find((part) => part.startsWith(prefix))
      ?.slice(prefix.length);
    return isSupportedThemePreference(saved) ? saved : null;
  } catch (_error) {
    return null;
  }
}

export function persistThemePreference(cookieDocument, preference) {
  if (!cookieDocument || !isSupportedThemePreference(preference)) {
    return;
  }
  try {
    cookieDocument.cookie = `${THEME_COOKIE_NAME}=${preference}; Max-Age=31536000; Path=/; SameSite=Lax`;
  } catch (_error) {
    // Theme switching remains usable when the cookie cannot be saved.
  }
}

export function effectiveTheme(preference, mediaQuery) {
  if (preference === "dark") {
    return "dark";
  }
  if (preference !== "system") {
    return "light";
  }
  try {
    return mediaQuery?.matches ? "dark" : "light";
  } catch (_error) {
    return "light";
  }
}

export function nextThemePreference(preference) {
  const index = SUPPORTED_THEME_PREFERENCES.indexOf(preference);
  return SUPPORTED_THEME_PREFERENCES[(index + 1) % SUPPORTED_THEME_PREFERENCES.length];
}

function renderThemeButton(button, label, preference) {
  const nextPreference = nextThemePreference(preference);
  const labelKey = `theme.${preference}`;
  const destinationKey = `accessibility.switch_theme_to_${nextPreference}`;
  label.setAttribute("data-i18n", labelKey);
  label.textContent = t(labelKey);
  button.setAttribute("data-i18n-aria-label", destinationKey);
  button.setAttribute("data-i18n-title", destinationKey);
  button.setAttribute("aria-label", t(destinationKey));
  button.setAttribute("title", t(destinationKey));
}

export function initializeThemeUi({
  button,
  label,
  documentElement,
  cookieDocument,
  mediaQuery,
} = {}) {
  if (!button || !label || !documentElement) {
    throw new TypeError("button, label, and documentElement are required");
  }

  let preference = readSavedThemePreference(cookieDocument) || "system";

  const apply = () => {
    documentElement.dataset.theme = effectiveTheme(preference, mediaQuery);
  };
  const refresh = () => renderThemeButton(button, label, preference);

  apply();
  refresh();

  button.addEventListener("click", () => {
    preference = nextThemePreference(preference);
    persistThemePreference(cookieDocument, preference);
    apply();
    refresh();
  });

  const handleSystemThemeChange = () => {
    if (preference === "system") {
      apply();
    }
  };
  try {
    mediaQuery?.addEventListener?.("change", handleSystemThemeChange);
  } catch (_error) {
    // Theme selection remains usable when media-query events are unavailable.
  }

  return Object.freeze({
    getPreference: () => preference,
    refresh,
  });
}
