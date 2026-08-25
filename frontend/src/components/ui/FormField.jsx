import { Children, cloneElement, useId } from "react";

function FormField({
  label,
  description,
  error,
  children,
  className = "",
  settingKey,
}) {
  const generatedId = useId().replaceAll(":", "");
  const control = Children.only(children);
  const controlId = control.props.id || `field-${generatedId}`;
  const descriptionId = description ? `${controlId}-description` : undefined;
  const errorId = error ? `${controlId}-error` : undefined;
  const describedBy = [control.props["aria-describedby"], descriptionId, errorId]
    .filter(Boolean)
    .join(" ") || undefined;

  return (
    <label
      className={`ui-form-field${error ? " has-error" : ""} ${className}`.trim()}
      htmlFor={controlId}
      data-setting-key={settingKey}
    >
      <span className="ui-form-field-label">{label}</span>
      {cloneElement(control, {
        id: controlId,
        "aria-describedby": describedBy,
        "aria-invalid": error ? true : control.props["aria-invalid"],
      })}
      {description ? (
        <small className="ui-form-field-description" id={descriptionId}>
          {description}
        </small>
      ) : null}
      {error ? (
        <small className="ui-form-field-error" id={errorId}>
          {error}
        </small>
      ) : null}
    </label>
  );
}

export default FormField;
