import { useSyncExternalStore } from "react";

export type Mode = "dark" | "light";

const listeners = new Set<() => void>();

function current(): Mode {
  return document.documentElement.dataset.mode === "light" ? "light" : "dark";
}

export function setMode(mode: Mode) {
  document.documentElement.dataset.mode = mode;
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", mode === "dark" ? "#09090B" : "#F6F6F7");
  try {
    localStorage.setItem("stash-mode", mode);
  } catch {
    /* private mode */
  }
  listeners.forEach((l) => l());
}

export function useMode(): Mode {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    current,
    () => "dark",
  );
}
