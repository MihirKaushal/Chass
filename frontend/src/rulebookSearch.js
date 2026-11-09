function collectSearchText(value, parts) {
  if (value === null || value === undefined) return;
  if (["string", "number", "boolean"].includes(typeof value)) {
    parts.push(String(value));
    return;
  }
  if (Array.isArray(value)) {
    value.forEach((item) => collectSearchText(item, parts));
    return;
  }
  if (typeof value === "object") {
    Object.values(value).forEach((item) => collectSearchText(item, parts));
  }
}

export function matchesRulebookSearch(query, ...values) {
  const normalizedQuery = query.trim().toLocaleLowerCase();
  if (!normalizedQuery) return true;
  const parts = [];
  values.forEach((value) => collectSearchText(value, parts));
  return parts.join(" ").toLocaleLowerCase().includes(normalizedQuery);
}
