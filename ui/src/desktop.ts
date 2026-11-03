/**
 * The desktop window's own commands (desktop/src-tauri/src/main.rs). In the window Tauri gives
 * the page `__TAURI_INTERNALS__`; in a browser it is absent, and so is the update button.
 */

interface TauriInternals {
  invoke<T>(command: string, args?: Record<string, unknown>): Promise<T>;
}

declare global {
  interface Window {
    __TAURI_INTERNALS__?: TauriInternals;
  }
}

function tauri(): TauriInternals | undefined {
  return window.__TAURI_INTERNALS__;
}

/** Tell whether the page shows in the desktop window, which can update the app. */
export function inDesktopWindow(): boolean {
  return tauri() !== undefined;
}

/** Return the newer version on the newest release page, or null when this one is newest. */
export async function newerVersion(): Promise<string | null> {
  const window = tauri();
  return window ? window.invoke<string | null>("update_version") : null;
}

/** Install the newer version; the window closes and opens again on it. */
export async function installUpdate(): Promise<void> {
  const window = tauri();
  if (window) {
    await window.invoke<null>("install_update");
  }
}
