export const SITE_SECTIONS = [
  {
    id: "home",
    label: "Home",
    href: "/",
    destination: "Home",
    leaveLabel: "Leave and go home",
  },
  {
    id: "customize",
    label: "Customize",
    href: "/customize",
    destination: "Customize",
    leaveLabel: "Leave and customize",
  },
  {
    id: "scanner",
    label: "Scanner",
    href: "/scanner",
    destination: "the Board Scanner",
    leaveLabel: "Open scanner",
  },
  {
    id: "rulebook",
    label: "Rulebook",
    href: "/rulebook",
    destination: "the Rulebook",
    leaveLabel: "Open rulebook",
  },
];

export function navigationDestination(href) {
  const path = (href || "").split(/[?#]/, 1)[0].replace(/\/$/, "") || "/";
  return (
    SITE_SECTIONS.find(
      (section) => (section.href.replace(/\/$/, "") || "/") === path,
    ) || { destination: "another page", leaveLabel: "Leave game" }
  );
}
