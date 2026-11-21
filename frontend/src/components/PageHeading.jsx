export default function PageHeading({ title, description, tagline, className = "", brand = false }) {
  return (
    <div className={`page-heading${brand ? " page-heading--brand" : ""} ${className}`.trim()}>
      <h1 className="page-heading-title">{title}</h1>
      {tagline ? <span className="page-heading-tagline">{tagline}</span> : null}
      <p className="page-heading-description">{description}</p>
    </div>
  );
}
