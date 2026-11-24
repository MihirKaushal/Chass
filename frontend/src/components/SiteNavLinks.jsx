import { shouldHandleAppLink } from "../routing";
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
      // Real links keep open-in-new-tab and link semantics; a plain click goes
      // through the page's handler so leave confirmations still apply.
      return (
        <a
          key={section.id}
          {...props}
          href={section.href}
          onClick={(event) => {
            if (!shouldHandleAppLink(event)) return;
            event.preventDefault();
            actions[section.id]();
          }}
        >
          {section.label}
        </a>
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
