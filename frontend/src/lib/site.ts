/** Public facts about the product, shared by the landing page, the footer and the legal pages. */

export const SITE = {
  name: "Stash",
  url: "https://stash.surajbayas.me",
  contactEmail: "surajyou45@gmail.com",
  legalUpdated: "31 October 2026",
};

export const FOOTER_LINKS: { title: string; links: { label: string; to: string }[] }[] = [
  {
    title: "Product",
    links: [
      { label: "Features", to: "/#features" },
      { label: "How it works", to: "/#how-it-works" },
      { label: "FAQ", to: "/#faq" },
      { label: "Get started", to: "/signup" },
    ],
  },
  {
    title: "Company",
    links: [
      { label: "About", to: "/about" },
      { label: "Contact", to: "/contact" },
    ],
  },
  {
    title: "Legal",
    links: [
      { label: "Privacy", to: "/privacy" },
      { label: "Terms", to: "/terms" },
    ],
  },
];
