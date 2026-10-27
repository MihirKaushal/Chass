export const SITE_SECTIONS = [
  {
    id: "home",
    label: "Home",
    href: "/",
    destination: "Home",
    leaveLabel: "Leave And Go Home",
  },
  {
    id: "customize",
    label: "Customize",
    href: "/customize",
    destination: "Customize",
    leaveLabel: "Leave And Customize",
  },
  {
    id: "scanner",
    label: "Scanner",
    href: "/scanner",
    destination: "the Board Scanner",
    leaveLabel: "Open Scanner",
  },
  {
    id: "rulebook",
    label: "Rulebook",
    href: "/rulebook",
    destination: "the Rulebook",
    leaveLabel: "Open Rulebook",
  },
];

export function navigationDestination(href) {
  const path = (href || "").split(/[?#]/, 1)[0].replace(/\/$/, "") || "/";
  return (
    SITE_SECTIONS.find(
      (section) => (section.href.replace(/\/$/, "") || "/") === path,
    ) || { destination: "another page", leaveLabel: "Leave Game" }
  );
}
