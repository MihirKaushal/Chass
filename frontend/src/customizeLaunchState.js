export function customizeLaunchState(validation, currentRequestKey) {
  const requestIsCurrent = Boolean(currentRequestKey)
    && validation?.requestKey === currentRequestKey;
  const requestFailed = validation?.status === "invalid"
    && !validation?.requestKey
    && Boolean(validation?.errors?.length);
  const checking = ["loading", "checking"].includes(validation?.status)
    || (!requestIsCurrent && !requestFailed);

  if (checking) {
    return {
      heading: "Checking Setup",
      detail: "Checking configuration...",
      errors: [],
      warning: "",
    };
  }

  if (validation?.valid) {
    return {
      heading: "Ready to Play",
      detail: "Configuration valid",
      errors: [],
      warning: validation?.warnings?.[0] || "",
    };
  }

  const errors = validation?.errors || [];
  const issueCount = errors.length;
  return {
    heading: issueCount
      ? `Fix ${issueCount} Issue${issueCount === 1 ? "" : "s"}`
      : "Setup Needs Attention",
    detail: issueCount
      ? "Click an issue below to review and fix the affected setting."
      : "Review the configuration before starting.",
    errors,
    warning: "",
  };
}
