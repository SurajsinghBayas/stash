// Apply the saved theme before first paint so there is no flash. A file, not an inline script, so the
// Content-Security-Policy can forbid inline scripts entirely.
try { var m = localStorage.getItem("stash-mode"); if (m === "light" || m === "dark") document.documentElement.dataset.mode = m; } catch (e) {}
