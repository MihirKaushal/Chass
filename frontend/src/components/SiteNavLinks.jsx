import { SITE_SECTIONS } from "../siteNavigation";
import AppLink from "./AppLink";

function SiteNavLinks({ active, onHome, onCustomize, tabs = false }) {
  const actions = { home: onHome, customize: onCustomize };
  return SITE_SECTIONS.map((section) => {
    const current = active === section.id;
    const props = {
      className: `${tabs ? "tab " : ""}site-nav-button${current ? " active" : ""}`,
      "aria-current": current ? "page" : undefined,
    };
    if (actions[section.id]) {
      return (
        <button
          key={section.id}
          {...props}
          type="button"
          onClick={actions[section.id]}
        >
          {section.label}
        </button>
      );
    }
    if (current)
      return (
        <span key={section.id} {...props}>
          {section.label}
        </span>
      );
    return (
      <AppLink key={section.id} {...props} href={section.href}>
        {section.label}
      </AppLink>
    );
  });
}

export default SiteNavLinks;
