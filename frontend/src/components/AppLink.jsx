import { navigate, shouldHandleAppLink } from "../routing";

function AppLink({ href, children, onClick, ...props }) {
  return (
    <a
      {...props}
      href={href}
      onClick={(event) => {
        onClick?.(event);
        if (!shouldHandleAppLink(event)) return;
        event.preventDefault();
        if (navigate(href)) {
          window.scrollTo({ top: 0, left: 0, behavior: "instant" });
        }
      }}
    >
      {children}
    </a>
  );
}

export default AppLink;
