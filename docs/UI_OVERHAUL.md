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

## 4. Known issues carried into later phases

| Issue | Where | Phase |
|---|---|---|
| The builder creates a new portfolio on every visit (19 duplicates for user 1) | `pages/PortfolioBuilder` `useEffect` | 3 |
| Onboarding invents a risk profile when the API fails | `pages/Onboarding` | 3 |
| Onboarding autofocuses its first input, so keyboard users skip past the skip link | `pages/Onboarding` | 3 |
| The main bundle is 923 kB because legacy routes eagerly import Recharts and framer-motion | `App.tsx` | 3 (route-level splitting) |
| The holdings table needs a stacked layout on phones; the specimen scrolls sideways inside its frame | `routes/styleguide`, future holdings view | 4 |
| Legacy `api/client.ts` and `store/useAdvisorStore.ts` are still used by the old pages | `src/api`, `src/store` | 3–4 |
| Asset-class sleeve is mirrored client-side from `policy.sleeve_of` | `lib/palette.ts` | 2 (B2 returns it) |

## 5. Remaining phases

- **Phase 1 (rest):** a light-theme page shell (masthead, navigation, footer) and the chart
  primitives: allocation strip, fan chart, and drift bars with table views.
- **Phase 2 (backend):**
  - B1 portfolio preview without persisting.
  - B2 construction snapshot and `/universe`.
  - B3 `/history` (value series).
  - B4 `/strategy/track-record` (the walk-forward backtest extended to risk 1–10).
  - B5 Monte Carlo goal probability, real terms and probability of loss.
  - B6 portfolio list with values.
- **Phase 3:** rebuild the journey (onboarding → proposal → confirm) on the typed layer.
- **Phase 4:** the portfolio workspace: performance, asset universe, future trajectory, activity.
- **Phase 5:** polish and QA, then a dark theme that redefines only the semantic tokens.

## 6. Figma

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
