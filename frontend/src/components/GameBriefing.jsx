import { buildGameBriefing } from "../gameSummary";

function GameBriefing({
  boardRows,
  boardCols,
  configuration,
  catalog,
  label = "Current Game",
  className = "",
}) {
  const briefing = buildGameBriefing({
    boardRows,
    boardCols,
    configuration,
    catalog,
  });

  return (
    <section className={`game-briefing ${className}`.trim()} aria-label={label}>
      <span>{label}</span>
      <strong>{briefing.title}</strong>
      <p>{briefing.summary}</p>
      {briefing.tags.length ? (
        <div className="game-briefing-tags">
          {briefing.tags.map((tag) => <small key={tag}>{tag}</small>)}
        </div>
      ) : null}
    </section>
  );
}

export default GameBriefing;
