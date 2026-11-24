import { useEffect } from "react";

import { SITE_TITLE } from "../documentTitle";

export default function useDocumentTitle(title) {
  useEffect(() => {
    document.title = title || SITE_TITLE;
  }, [title]);

  useEffect(() => () => {
    document.title = SITE_TITLE;
  }, []);
}
