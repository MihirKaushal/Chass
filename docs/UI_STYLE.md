# UI conventions

Chass uses a tan-and-blue theme with restrained decoration. Keep these conventions
when adding pages or controls; avoid styling each feature as a separate product.

- **Hierarchy:** use `PageHeading` for main page titles and one useful description.
  Home may use the larger wordmark and its slogan; play stays a compact toolbar.
- **Copy:** use sentence case for actions, status messages, and instructions.
  Preserve proper names such as Chass Gambit, Stockfish, and piece/ability names.
  Help text should explain a consequence or constraint, not repeat its label.
- **Actions:** use the shared `Button`. Solid blue marks the primary next action;
  secondary buttons handle alternatives, text buttons handle small utilities,
  and danger styling marks destructive actions. Selection color is separate
  from action priority. Local and online rooms are equally valid choices.
- **Surfaces:** quiet tan/light backgrounds for navigation and settings; strong
  blue for page identity or important status. Use an opaque background for
  floating menus so content behind them cannot interfere with readability.
- **Grouping:** retain outer cards for distinct choices. Inside a piece or ability
  card, use spacing and a divider for tuning fields instead of another box.
  Keep semantic fieldsets and legends even when removing visual borders.
- **Tokens:** use the color, spacing, typography, and radius variables in
  `frontend/src/styles/tokens.css`. Related controls get small gaps; sections
  get larger gaps. Use `--radius-control` for inputs/buttons and `--radius-lg`
  for cards, not arbitrary per-feature corner sizes.
- **Motion:** preserve the home logo and scanner highlight. Other animation
  should communicate loading, a state change, or actionable feedback, and
  respect reduced-motion preferences.
- **Verification:** retain keyboard focus, hover states, disabled states, menu
  contrast, and room for changing status text. Run frontend tests, production
  build, and Playwright; inspect screenshots as well as passing assertions.

`frontend/e2e/page-headings.spec.js` and `ui-consistency.spec.js` cover shared
headings, action hierarchy, keyboard search, and viewport overflow.
