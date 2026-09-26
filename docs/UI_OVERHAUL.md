# UI Overhaul: "The Statement" (September 2026)

The frontend is being rebuilt so that a portfolio reads like a well-kept statement. Every figure
sits in its column, colour always stands for something, and each number says where it came from.
This file records the design decisions and how they were checked. It also tracks the phases.

- Specimen of every token and primitive: run `npm run dev` and open `/styleguide`.
- Branch: `feat/ui-overhaul`.

## 1. Principles

1. **Colour is meaning.**
   - Growth holdings are verdigris and defensive holdings are ochre.
   - Losses are claret with a "−" sign. Gains stay ink with a "+" sign, which is the accounting
     convention.
   - The ink-blue accent is reserved for actions and focus. Nothing else gets colour.
2. **Ranges, not points.** Projections are shown as a spread with the middle marked, never as a
   single line.
3. **Provenance on every figure.** Each figure that is not a plain account fact is labelled
   *measured*, *simulated* or *estimated*. A small mark differs by shape as well as by the word
   (filled, half or open).
4. **Figures are set in the serif; words in the grotesk.**
   - Newsreader Variable (optical sizes 6–72) is used for headlines and for every figure in a
     column or headline.
   - Schibsted Grotesk Variable is used for text and controls.
   - The reason: Schibsted's tabular figures also widen `. , :` to digit width ("£39, 846"),
     while Newsreader's do not. Figures inside running text stay proportional in the text face.
   - Both fonts are self-hosted through `@fontsource-variable`. There are no Google Fonts
     requests.

## 2. Palette and how it was verified

Tokens are in `frontend/src/styles/tokens.css`. The chart hexes are mirrored in
`frontend/src/lib/palette.ts`.

| Check | Tool | Result |
|---|---|---|
| Text contrast | Unit test (`palette.test.ts`, parses `tokens.css`) | Ink, ink-2, ink-3, accent, loss, ok and warn are ≥ 4.5:1 on paper, sheet and sunk, and on their own washes |
| Control boundaries | Same test | `--color-rule-strong` is ≥ 3:1 on all surfaces (WCAG 1.4.11) |
| Growth / defensive ramps | dataviz `validate_palette.js --ordinal` | Monotone lightness, ΔL ≥ 0.06, light end ≥ 2:1 on paper |
| Growth vs defensive under colour blindness | dataviz validator, pairwise at equal lightness | ΔE 9.6–12.7 (deutan/protan) at hue 182 vs 58. The first choice, green 152 vs ochre 72, scored only 4.4–7.6, so the green moved to verdigris |
| Categorical (comparisons) | dataviz validator, light mode | Every check passes. Worst adjacent CVD ΔE is 10.6; normal-vision ΔE is 15.6. Slot 3 (ochre) is 2.9:1 on paper, so it always carries a label |

- Allocation strips place the two ramps side by side.
- The ramps are ordinal, so neighbouring steps are close by design.
- Every such chart therefore separates segments with a paper gap and labels them (a legend or
  direct labels, plus a table view).
- `palette.ts` states the same rule.

## 3. Phase 0: foundations (done)

- **Tooling:**
  - ESLint 9 flat config.
  - Vitest with jsdom and Testing Library, with an 80% coverage gate over the new modules.
  - Playwright on installed Chrome, desktop and mobile.
  - `tsconfig.node.json`, so configs and e2e specs are type-checked.
  - `npm run check`.
- **Typed API layer** (`src/api/`):
  - `http.ts` parses every response with zod. It raises `ApiError` with the kind `http`,
    `network` or `contract`, and passes aborts through untouched.
  - `schemas.ts` mirrors `backend/api/models.py` and the dict routes. Nullability follows the DB
    columns.
  - `endpoints.ts` has one function per route.
  - `queries.ts` holds the react-query keys and hooks:
    - Keys are hierarchical per portfolio, so a mutation invalidates every view of that portfolio.
    - Only network failures and 5xx responses are retried.
- **Session state** (`src/store/session.ts`):
  - Identity (user and last portfolio) is kept in localStorage.
  - The onboarding draft is kept in sessionStorage.
  - Both are validated with zod on load, and malformed data is discarded.
  - Everything else is server state.
- **Formatting** (`src/lib/format.ts`):
  - en-GB money, compact money (k/m/bn), percentages, percentage points and dates.
  - A true minus sign, no "−£0", and an em dash for missing values.
- **Primitives** (`src/ui/`):
  - Button and ButtonLink; Field and TextInput; Stat, StatGroup and Delta; Tag and Provenance;
    ErrorBoundary.
  - Targets are ≥ 44 px, and there is one visible focus ring.
  - Hint and error are wired through `aria-describedby`.
- **Legacy bridge:**
  - `src/styles/legacy.css` maps the old token names onto the new ones.
  - Existing pages therefore render in the light palette without gradient text, glows or glass.
  - The chart colours on those pages follow the growth/defensive rule.
  - Delete the file once the last legacy page is rebuilt.
- **Legacy fixes along the way:**
  - The History page crashed when opening a saved portfolio, because a partial record was loaded
    as a full result. It also printed "Invalid Date" and could crash on a null expected return.

## 4. Phase 1: page shell and chart primitives (done)

- **Page shell** (`src/routes/AppShell.tsx`):
  - A layout route containing the skip link, the masthead (wordmark, Portfolios, Dashboard and
    one primary action, "Build a portfolio"), `<main id="main">` and the small print.
  - The current page is marked with `aria-current` and an ink underline, not by colour alone.
  - On phones the navigation drops to its own row; there is no hamburger menu.
  - Rebuilt screens mount inside it; `/styleguide` is the first. Legacy screens keep their own
    chrome through `LegacyLayout` in `App.tsx` until they are rebuilt.
- **Chart primitives** (`src/charts/`):
  - Hand-rolled SVG and HTML on `d3-scale` and `d3-shape`. Recharts stays only on legacy pages.
  - `ChartFrame` provides the title, provenance, summary sentence, a Chart/Table switch, legend
    and notes. It dims the last render while a refetch is pending and shows an empty state.
  - `AllocationBar`:
    - A 100% strip, growth first, with 2 px surface gaps between segments.
    - Brackets above the strip mark the growth/defensive split; every holding is listed below.
  - `FanChart`:
    - Bands for 10–90 and 25–75, the median as the only line, and paid-in as a dashed reference.
    - An optional goal rule, and labels at the end of the median and outer lines.
  - `LineChart`:
    - Values over time, with line, area (drawn to zero) and reference variants.
    - An optional labelled baseline, end labels, and table rows sampled from long series.
  - `DriftBars`:
    - Drift from target on a centred axis, with the rebalancing band shaded.
    - A holding outside its band says "Outside band" in words, with an icon.
  - `DataTable` and `FundCell`: the statement-style table behind every Table view.
- **Interaction and accessibility:**
  - The crosshair readout lists every series at the cursor, in legend order.
  - Keyboard control: arrows, Page Up/Down, Home/End and Escape. Focus starts on the latest point.
  - Keyboard moves are announced through a polite live region. The visual tooltip is
    `aria-hidden`.
  - Each plot is a focusable `role="img"` whose name summarises the takeaway.
- **Typography:** headline figures (`Stat`) are now proportional; tabular figures are kept for
  columns. Axis labels stay in the grotesk with proportional figures, and end labels use the serif.
- **Tests:**
  - Unit tests for scales, the data model, hooks, every chart (table twin, keyboard readout,
    pointer, empty state) and the shell.
  - A contract test parses the recorded live API responses (§9).
  - e2e: the shell, keyboard readout on the fan chart, and the table switch.
  - Coverage over the new modules: 98.8% of lines and 94% of branches.

## 5. Phase 2: backend for the workspace (done)

| Route | What it returns |
|---|---|
| `POST /api/portfolio/preview` | Builds a portfolio without saving it: allocations with sleeves, policy, frontier point, and whether the risk was capped to the stored profile. Builds are cached per risk score for 6 hours, so opening the same proposal reuses it. |
| `GET /api/portfolio/{id}/construction` | The snapshot stored when the portfolio was opened: each fund's expected return and calibrated volatility, correlations, policy and frontier. `recorded: false` for portfolios opened before snapshots existed. |
| `GET /api/universe[?portfolio_id]` | The building blocks: each asset class, its role and rule, and its funds. With a portfolio, it also marks what the portfolio holds and targets. |
| `GET /api/portfolio/{id}/history` | Daily value, amount invested, cash, net contributions and cumulative time-weighted return, replayed from the ledger. It never back-fills prices. |
| `GET /api/strategy/track-record?risk=1..10` | The walk-forward backtest from `backend/data/track_record.json` (built by `make track-record`), with the two-fund benchmark, calendar years and summary statistics. |
| `POST /api/monte-carlo` | Now also takes `annual_return` and `annual_volatility` (for previews), `goal_amount` and `real_terms`. It returns paid-in by year, probability of loss by year and overall, and the inflation rate used. |
| `GET /api/portfolios/user/{id}` | Newest first, each with its current value, net contributions, return and holdings count. Values are null for legacy portfolios. |

At risk levels 1–8 the track record trails its benchmark, mostly because of 2022. The workspace
must show this as plainly as the years it leads.

## 6. Known issues carried into later phases

| Issue | Where | Phase |
|---|---|---|
| The builder creates a new portfolio on every visit (19 duplicates for user 1) | `pages/PortfolioBuilder` `useEffect` | 3 (use `usePreview`, create only on confirm) |
| Onboarding invents a risk profile when the API fails | `pages/Onboarding` | 3 |
| Onboarding autofocuses its first input, so keyboard users skip past the skip link | `pages/Onboarding` | 3 |
| The main bundle is 931 kB because legacy routes eagerly import Recharts and framer-motion | `App.tsx` | 3 (route-level splitting) |
| The holdings table needs a stacked layout on phones; the specimen scrolls sideways inside its frame | `routes/styleguide`, future holdings view | 4 |
| Legacy `api/client.ts` and `store/useAdvisorStore.ts` are still used by the old pages | `src/api`, `src/store` | 3–4 |
| `palette.sleeveOf` still mirrors `policy.sleeve_of`; preview and snapshot now return `sleeve`, so new screens should read it from the API | `lib/palette.ts` | 3–4 (delete once the legacy pages go) |
| All 19 local portfolios predate snapshots and the ledger replay, so construction and history are empty for them | local database | Open a new portfolio to see both |

## 7. Remaining phases

- **Phase 3:** rebuild the journey (onboarding → proposal → confirm) on the typed layer, inside
  the shell: a live preview while the risk slider moves, and creation only on confirm.
- **Phase 4:** the portfolio workspace, built from the Phase 1 primitives and Phase 2 routes:
  - Performance: `LineChart` over `/history`, with the value and invested series.
  - Asset universe: `AllocationBar`, `DriftBars` and `/universe`.
  - Future trajectory: `FanChart` over `/monte-carlo`, in real terms, with the goal.
  - Track record: `LineChart` over `/strategy/track-record`, strategy against benchmark.
  - Activity: the transaction ledger.
- **Phase 5:** polish and QA, then a dark theme that redefines only the semantic tokens.

## 8. Figma

- Figma is connected: the "Vansh" account, Starter plan, with a **View** seat.
- A View seat on Starter cannot edit design files, and MCP calls are rate-limited. Nothing has
  been written to Figma yet.
- With an editor seat, the useful next steps are:
  1. **Mirror the tokens as Figma variables** (`figma-generate-library`), with light and dark
     modes.
  2. **Push `/styleguide` and each rebuilt page to a Figma file** for review
     (`figma-generate-design`).
  3. **Draw the new journey as a FigJam flow** (`figma-generate-diagram`).
  4. **Link the primitives with Code Connect** once they are stable.

## 9. Contract samples

`frontend/src/test/contract/*.json` are responses recorded from the running API.
`src/api/contract.test.ts` parses each one with the schema the app uses, so a backend change
that breaks the client fails in CI rather than in the browser. After changing a response model,
start the API (`make backend`) and record again:

| File | Request |
|---|---|
| `preview.json` | `POST /api/portfolio/preview` for user 1, risk 9 (capped to 7), £50,000 |
| `construction.json` | `snapshot_from_result(build_optimised_portfolio(7, 1.0), 7)` wrapped in `ConstructionResponse` (no local portfolio has one yet) |
| `construction-legacy.json`, `history-legacy.json` | `GET /api/portfolio/19/construction`, `GET /api/portfolio/19/history` |
| `universe.json` | `GET /api/universe?portfolio_id=19` |
| `track-record.json` | `GET /api/strategy/track-record?risk=5` |
| `monte-carlo.json` | `POST /api/monte-carlo` over 15 years with `annual_return`, `annual_volatility`, `goal_amount` and `real_terms: true` |
| `portfolios.json`, `risk-profile.json` | `GET /api/portfolios/user/1`, `GET /api/risk-profile/1` |
