function pluralizeCopy(copy) {
  return copy.replace(
    /\b(\d+) ((?:own |Cannibal |affected-player |allied )?)(square|turn|move|blocker|time|use|pacification|piece)\(s\)/g,
    (_, rawValue, modifier, unit) => (
      `${rawValue} ${modifier}${Number(rawValue) === 1 ? unit : `${unit}s`}`
    )
  );
}

export function renderTuningTemplate(template, values) {
  if (!template) return "";
  const rendered = template.replace(/\{([A-Za-z0-9_]+)\}/g, (match, key) => (
    values[key] ?? match
  ));
  return pluralizeCopy(rendered);
}

export function scorchUsageDefault(rows, cols) {
  return Math.max(1, Math.floor((Math.sqrt(rows * cols) / 4) + 0.5));
}

export function parameterDefault(parameter, context = {}) {
  if (parameter.dynamicDefault === "board_sqrt_quarter") {
    return scorchUsageDefault(context.rows ?? 8, context.cols ?? 8);
  }
  return parameter.default;
}

export function parameterDefaults(entries, context = {}) {
  return Object.fromEntries(
    entries.map((entry) => [
      entry.type || entry.id,
      Object.fromEntries(
        (entry.tunableParameters || []).map((parameter) => [
          parameter.id,
          parameterDefault(parameter, context),
        ])
      ),
    ])
  );
}

export function mergeParameterGroups(defaults, supplied = {}) {
  return Object.fromEntries(
    Object.entries(defaults).map(([ownerId, values]) => [
      ownerId,
      { ...values, ...(supplied?.[ownerId] || {}) },
    ])
  );
}

export function effectiveCatalogEntry(entry, configured = {}) {
  if (!entry) return entry;
  const values = {
    ...Object.fromEntries(
      (entry.tunableParameters || []).map((parameter) => [
        parameter.id,
        parameter.default,
      ])
    ),
    ...configured,
  };
  const result = {
    ...entry,
    description: renderTuningTemplate(
      entry.descriptionTemplate || entry.description,
      values
    ),
    movement: renderTuningTemplate(
      entry.movementTemplate || entry.movement,
      values
    ),
    rules: (entry.ruleTemplates?.length ? entry.ruleTemplates : entry.rules || []).map(
      (rule) => renderTuningTemplate(rule, values)
    ),
    summary: renderTuningTemplate(entry.summaryTemplate || entry.summary, values),
    details: (entry.detailTemplates?.length ? entry.detailTemplates : entry.details || []).map(
      (detail) => renderTuningTemplate(detail, values)
    ),
    configuredParameters: (entry.tunableParameters || []).map((parameter) => ({
      ...parameter,
      value: values[parameter.id],
    })),
  };
  if (entry.cooldownTurnsParameter) {
    result.cooldownTurns = values[entry.cooldownTurnsParameter];
  }
  if (entry.usageLimitParameter) {
    result.usageLimit = values[entry.usageLimitParameter];
  }
  return result;
}

export function parameterValueLabel(parameter, value = parameter.value) {
  const unit = parameter.unit || "value";
  return `${value} ${Number(value) === 1 ? unit : `${unit}s`}`;
}
