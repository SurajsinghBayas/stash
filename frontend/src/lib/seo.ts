import { useEffect } from "react";
import { SITE } from "./site";

export const DEFAULT_TITLE = "Stash · Everything you save, on one canvas";
export const DEFAULT_DESCRIPTION =
  "Save links, notes, code and images on one visual canvas. Ask a question and Stash answers from your own cards, " +
  "pointing at each one. Reminders reach your inbox on time. Free to use.";

function setMeta(attr: "name" | "property", key: string, content: string) {
  let el = document.head.querySelector<HTMLMetaElement>(`meta[${attr}="${key}"]`);
  if (!el) {
    el = document.createElement("meta");
    el.setAttribute(attr, key);
    document.head.appendChild(el);
  }
  el.content = content;
}

function setCanonical(href: string) {
  let el = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
  if (!el) {
    el = Object.assign(document.createElement("link"), { rel: "canonical" });
    document.head.appendChild(el);
  }
  el.href = href;
}

/**
 * Title, description, canonical URL and social tags for a public page. index.html carries the same defaults for
 * crawlers that don't run JavaScript (link previews); this keeps them right per page for search engines that do.
 */
export function useSeo({ title, description = DEFAULT_DESCRIPTION, path }: { title?: string; description?: string; path: string }) {
  useEffect(() => {
    const full = title ? `${title} · ${SITE.name}` : DEFAULT_TITLE;
    const url = `${SITE.url}${path}`;
    document.title = full;
    setMeta("name", "description", description);
    setMeta("property", "og:title", full);
    setMeta("property", "og:description", description);
    setMeta("property", "og:url", url);
    setMeta("name", "twitter:title", full);
    setMeta("name", "twitter:description", description);
    setCanonical(url);
    return () => {
      document.title = SITE.name;
      setMeta("name", "description", DEFAULT_DESCRIPTION);
      setCanonical(`${SITE.url}/`);
    };
  }, [title, description, path]);
}
