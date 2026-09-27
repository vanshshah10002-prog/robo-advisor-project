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
  - A contract test parses the recorded live API responses (§10).
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

## 6. Phase 3: from the front page to an opened portfolio (done)

Every legacy screen is gone. The journey runs inside the shell, on the typed client, and nothing
is saved until the investor presses "Open portfolio".

| Route | What it does |
|---|---|
| `/` | "A portfolio you can read": how it works in three steps, then the walk-forward track record told as a sentence built from its figures, whichever way they fall ("A simple two-fund portfolio … did better"), with a level switch (3, 5, 7, 9) and the week-by-week chart. A returning investor gets "Go to your portfolio". |
| `/start`, `/start/losses`, `/start/finances` | Three short steps: your goal, ups and downs, your finances. Every question is asked once: the horizon question is answered from the years typed, and the emergency-fund check from the savings question. Numbered answers take the keys 1–5. A blank Continue lists every problem at the top, takes focus there, and links to each field. A step left incomplete sends you back to it before anything is sent. The draft lives in `sessionStorage` and is validated with zod on load. |
| `/start/result` | The level, and the willingness and capacity scores behind it, with the rule that joins them. The growth/defensive split comes from a real preview. "How far level N has fallen before" uses the nearest tested level and says so when yours lies between two (the backtest covers whole levels only). If the questions or the profile fail to load, the page says so and offers a retry; it never invents a result. |
| `/proposal` | An unsaved preview: amount, monthly amount, ISA or general account, and a risk slider that stops at the assessed level ("You can take less risk than that, not more"). It opens with one sentence ("£50,000 now and £250 a month, at risk level 4: 40% in growth…, 9 funds costing about £52 a year"), then expected return, yearly swing, fund costs in pounds, the chance of ending below what was paid in, the holdings, the funds and a real-terms projection. Changes settle for 450 ms before a rebuild; the last proposal stays on screen, dimmed, with a polite status line. "Open portfolio" is enabled only when the proposal on screen is exactly what the inputs ask for, and it opens that request. |
| `/portfolio/:id` | A minimal, honest overview until Phase 4: a sentence ("Worth £49,950 on 26 Sept 2026: £50 less than the £50,000 paid in. Every holding is within its band."), value, paid in, gain, rebalance status, unpriced funds, holdings and drift. Portfolios opened before purchases were recorded say so instead of showing a £0 value as a loss. |
| `/portfolios` | Every portfolio opened in this browser, with value, paid in and return, and "Not valued" where there is no value. |
| Old addresses | `/onboarding` goes to `/start`; `/assets`, `/invest`, `/builder` and `/review` go to `/proposal`; `/history` goes to `/portfolios`; `/dashboard` goes to the last portfolio opened, or the list. Anything else shows "There is nothing at this address". |

- **Shell:**
  - The navigation is now "How it works" and "Portfolios". "Build a portfolio" leads to `/start`
    and is hidden during the journey.
  - Each page is lazy-loaded behind a keyed error boundary, so a failing page keeps the masthead
    and there is still only one `<main>`.
  - Moving to another page starts it at the top, with focus on `<main>`. A page that has already
    placed focus inside itself, such as an error summary, keeps it. The first page is left alone,
    so Tab still reaches the skip link.
  - Every page sets the document title ("Your goal · UK Robo Advisor").
- **New controls** (`src/ui/`):
  - `ChoiceGroup`: real radios, a fieldset legend, and number keys.
  - `Slider`: a native range over fixed stops, with `aria-valuetext`.
  - `Notice` and `ErrorSummary`: only errors are alerts; the summary takes focus.
  - `MoneyField`: keeps what was typed and reports the parsed figure.
- **Removed:**
  - `src/pages/*`, `api/client.ts`, `store/useAdvisorStore.ts` and `styles/legacy.css`;
  - Recharts, framer-motion, react-hook-form, `@hookform/resolvers` and date-fns.
  - The entry chunk is now 355 kB (108 kB gzipped), and each page is its own chunk.
- **Backend:**
  - **Real-terms Monte Carlo:** contributions rise with inflation, so in today's money each
    payment counts at face value. `summarise_paths` used to deflate paid-in along with the values,
    which made the dashed paid-in line fall. The loss probability now compares the two on that
    same basis. For the recorded sample (£50,000 and £250 a month for 15 years), the chance of
    ending below paid-in is 6.2%, where the old basis said 0.6%.
  - `/api/asset-classes` names `europe_ex_uk_equity` ("Europe ex-UK Equity"). It had fallen back
    to a title-cased id, "Europe Ex Uk Equity". `europe_equity`, which includes the UK, was
    mislabelled "ex-UK" and is now "Europe Equity".
- **Tests:**
  - 375 unit and route tests. Route tests render the whole app against a stubbed `fetch`
    (`src/test/app.tsx`).
  - Coverage over `src/routes/**`, `src/ui/**`, `src/lib/**`, `src/charts/**` and the API layer
    is 99.6% of lines and 96.0% of branches.
  - e2e (`e2e/journey.spec.ts`) walks from the front page to an opened portfolio on desktop and
    on a phone, against a stubbed API. It checks the requests sent, sideways scrolling and console
    errors.
  - 154 backend tests.
- **Found while testing and in review:**
  - Clearing the amount on the proposal left "Open portfolio" enabled for 450 ms, which would
    have opened the previous amount.
  - While an amount is invalid, the proposal now keeps its last valid figures, dimmed, and says
    so. Before, it showed them with no warning and then changed the heading to "Building your
    portfolio". Arriving with no amount (the draft lives only for the browser session) asks for
    one.
  - Stat values sat at different heights when a label wrapped; `Stat` now aligns its rows through
    a subgrid.

## 7. Phase 4: the portfolio workspace (done)

An opened portfolio is now a workspace: one line saying which portfolio it is ("Portfolio 20 ·
risk level 4 · ISA · £250 a month"), five sections, and the section. The valuation loads once in
the layout and is shared, so moving between sections never waits for it again. Each section
opens with a sentence built from its own figures, and each has its own route, title and chunk.

| Route | What it shows |
|---|---|
| `/portfolio/:id` | Overview: value at the stored closing prices, paid in, gain, "Update prices" (fetches the latest closes and says which), rebalance status with a link to the trades, holdings and drift. |
| `/portfolio/:id/performance` | The measured record, replayed from the ledger: return since opening (time-weighted), gain, worst fall from a high, and the return expected when opened against what has been realised (only after a year). Value against paid-in and a drawdown chart, for 1 month, 3 months, this year, 1 year or since opening (only the periods the history covers). Returns by period, with a yearly average after a year. Gain or loss by holding: cost, gain, gain on its cost and what it added to the return. Then the simulated record of the same rules at the nearest tested level, labelled as not this portfolio's history. |
| `/portfolio/:id/universe` | All 13 building blocks, growth then defensive, held or not: the job each does, its limit, target, expected return and yearly swing (calibrated), share of the risk, and the fund held with ISIN, yearly cost, size, domicile and factsheet. It says why a block is not held (no weight at this level, or no fund with enough history) and why a fund other than the first choice is held. "Where the risk comes from" compares each holding's share of the money with its share of the risk (w·Σw / w′Σw from the snapshot), then where the shares are by region, then the correlations between the funds held. |
| `/portfolio/:id/outlook` | A 2,000-path projection from today's value, using the expected return and swing stored when it opened: years (defaulting to the horizon given in the risk profile, else 10), monthly amount, an optional goal, and today's money or pounds of the day. It gives the middle outcome, paid in by then, the chance of ending below it and of reaching the goal, the fan, how the chance of a loss changes over the years, and how often the backtest's forecasts held (60% within one swing, where a well-judged forecast manages about 68%). |
| `/portfolio/:id/activity` | Add money (paid in, then invested where the portfolio is furthest below target); check a rebalance and see every trade with its cost and any gain realised, with the ISA or capital gains tax position, before running it; and every transaction, newest first. |
| `/portfolios` | Each portfolio now has a small trend line of its value since opening. |

- **Charts:**
  - `Heatmap`: a correlation grid with every figure printed and a table twin. Its image label
    names the closest and the most independent pair. On phones the tickers head the rows, and
    the column heads read upwards.
  - `CompareBars`: two measures per row on one scale, each bar carrying its figure.
  - `Sparkline`: a labelled trend line for a table cell.
  - `DataTable` has a `stack` mode. On phones each row becomes a block of labelled values, so
    the ledger, trades, gains and list never scroll sideways. The table roles are restated
    because the stacked layout would drop them.
  - Time axes drop a label that would overlap its neighbour. On a phone, "Jul 2025" had run into
    "Oct 2025".
  - `AllocationBar` leaves out the growth/defensive bracket when every item is in one sleeve.
- **Found in review:**
  - If the portfolio's details failed to load, the Outlook projected with no monthly amount and
    said nothing. The workspace now shows the failure with a retry, and the Outlook waits for the
    details.
  - The drawdown series was quadratic in the length of the history; it is now a single pass.
  - A hedge whose share of the risk is below zero draws no bar and is described as lowering the
    risk.
- **Shell:** the error boundary now resets when the address changes instead of being keyed by
  it. Before, moving between sections remounted the whole workspace, which lost the navigation's
  focus and anything typed in a section. The workspace is keyed by portfolio instead, so nothing
  typed in one portfolio carries over to another.
- **Backend:**
  - **Users are no longer matched by name.** `POST /risk-profile` and `/risk-profile/quick`
    take the `user_id` this browser was given. With it, they update that user, even after a
    rename. Without it, or with an unknown id, they start a new one. Two people who both type
    "Ada" no longer share portfolios.
  - `/performance` returns each holding's `sleeve`, so `palette.sleeveOf` is gone.
  - `/monte-carlo` with a `portfolio_id` refuses with 422 when the portfolio has no stored
    expected return and volatility. Before, it silently used 6% and 12%.
  - `/asset-classes` names the 13 building blocks as the universe does ("US shares", not "US
    Equity"), so a holding has one name on every page.
  - The factsheet links for SGLP.L (Invesco gold, which pointed at an iShares silver page) and
    ISPY.L (L&G cyber security, which pointed at an iShares small-cap page) are cleared rather than
    left wrong. A test now checks that every link goes to the fund's own issuer.
- **Tests:**
  - Unit and route tests for every section and chart. The route tests stub a 15-month history, a
    universe held exactly as the recorded construction snapshot holds it, the ledger, a
    rebalance plan and the projection.
  - e2e (`e2e/workspace.spec.ts`) walks every section, adds money and runs a rebalance on
    desktop and on a phone, checking sideways scrolling and console errors. It found the risk
    bars' figures spilling 24px past a phone's edge.
  - `tests/test_workspace.py` covers user ids, sleeves and the saved-portfolio projection.

## 8. Phase 5: polish and QA (done)

### Dark theme

"Appearance" in the small print offers Match device, Light and Dark. The choice is kept in this
browser (`ukra.theme`). The dark theme is warm near-black paper with warm ink, not an inversion.
It redefines only the semantic, chart and shadow tokens, under `:root[data-theme='dark']`.
`palette.test.ts` enforces two rules:
- the dark block redefines nothing else;
- every literal light colour has a dark counterpart.

It is measured by the same rules as the light theme, in the same test for both blocks:

| Check | Light | Dark |
|---|---|---|
| Ink, ink 2, ink 3 on paper | 15.6, 7.7, 5.5:1 (ink 3 is 5.0:1 on sunk) | 15.5, 10.1, 6.4:1 (ink 3 is 6.8:1 on sunk) |
| Accent on paper | 7.2:1 | 8.6:1 |
| Control boundary on paper | 3.3:1 | 3.9:1 |
| Growth vs defensive, same step, CIEDE2000 under simulated deuteranopia / protanopia | worst 24.4 / 18.3 | worst 24.8 / 17.9 |
| Ramps | darkest step first, ΔL ≥ 0.06 | brightest step first, ΔL ≥ 0.06 |
| Comparison colours on paper | 2.9–6.9:1 (slot 3 always labelled) | 7.1–9.7:1, within one lightness band |
| Ink on every heatmap shade | ≥ 4.5:1 | ≥ 4.5:1 |

The simulations are Machado et al. (2009) at full severity. The check script is not in the
repository; the contrast rules are, in `palette.test.ts`.

- **Charts follow the theme.**
  - `palette.ts` hands out token references (`var(--chart-cat-1)`), not hexes.
  - Marks draw them through `style`, because SVG presentation attributes do not reliably resolve
    `var()`. A theme switch therefore recolours every mark without re-rendering.
  - Heatmap cells mix the two heat tokens with `color-mix()`.
  - Each theme's literal hexes stay in `THEME_COLOURS`, for the tests.
- **No flash of the wrong theme.**
  - An inline script in `index.html` sets `data-theme` before first paint, from the saved choice
    or the device setting.
  - It also sets the browser's `theme-color` and `color-scheme`. `src/lib/theme.ts` takes over
    after that, and follows a choice made in another tab.
  - `theme.test.tsx` runs the real script.
  - A browser test (`e2e/theme.spec.ts`) blocks the app's own code on reload and checks that the
    theme still arrives.
- **The style guide shows the theme in effect.** It reads each token's value back from the page
  instead of printing a copy of the light hexes.

### Archive

- **What it does.** A portfolio can be archived from the list. That takes it off the list and
  deletes nothing: it still opens, with its ledger and history.
- **On the list.** A notice confirms the change and offers Undo. It takes focus, because the button
  that was pressed has gone with its row. Archived portfolios are listed underneath, with Restore.
- **While a request runs,** the pressed row's button shows it is working and the other rows wait.
- **When everything is archived,** the list says so rather than that nothing was ever opened.
- **"Your portfolio".** If the archived portfolio was the one the front page links to, that link
  moves to the newest portfolio left, or goes away.
- **In the workspace,** an archived portfolio says so at the top, with Restore.
- **Backend:**
  - `POST /portfolio/{id}/archive` and `/restore`. Both are safe to repeat, and archiving again
    keeps the first date.
  - `GET /portfolios/user/{id}/archived`, a path of its own so request stubs cannot confuse it
    with the list.
  - `archived` and `archived_at` on the detail, and `archived_at` on list rows.
  - A new `archived_at` column, added to existing databases by `_add_missing_columns`.
  - A row whose active flag was never set counts as on the list, so no portfolio falls between the
    two lists. Archiving is keyed off `archived_at`.
  - `tests/test_archive.py`, including a test that an archived portfolio still takes money.

### Motion

- **One staged reveal per page.** The first blocks of each workspace section, the list, the result
  and the proposal rise into place in turn (`.stagger` in `base.css`). Everything is in place by
  540 ms.
- **The Overview's value settles into place** over 0.7 s, from nine-tenths of the figure
  (`CountUp`). While it counts, the moving digits are hidden from assistive technology, which reads
  the figure once.
- **Reduced motion.** Both are off when the reader asks for less motion, and the count is also off
  where the browser cannot say. The reduced-motion rule now also removes animation delays.

### Accessibility

- **axe.** `e2e/a11y.spec.ts` runs axe over 12 pages, in both themes, on desktop and on a phone,
  against WCAG 2.2 A and AA. The dark runs reach the theme the way a reader would, through the
  device setting. There are no violations.
- **What axe found:** one violation. The Activity trades table was wider than its panel on desktop,
  so it scrolled, but a keyboard could not reach it to scroll.
- **The fix.** `DataTable` now measures itself. While it scrolls sideways it is a named region in
  the tab order, with a focus ring. Tables that fit add no tab stop.

### Screenshots and copy

- **Screenshots.** Every page at 390, 768 and 1280 px, in both themes, against the local API.
  Nothing scrolls sideways at any width.
- **What they found.** On Performance, "Return since opening −0.1%" sat beside "Gain +£57" with
  nothing to say why. Both are right: the return runs to the first recorded close, after opening
  costs; the gain uses the latest prices. Each now says which moment it is measured at, and the
  one-close headline was reworded.
- **Copy.** A sweep for pleas, exclamations, "click here" and US spellings found none. The theme is
  called "dark" everywhere, matching the switch.

### Tests

At the end of the phase:
- 584 unit tests, covering 99.7% of statements and 95.2% of branches;
- 72 browser checks;
- 172 backend tests.

## 9. Known issues

| Issue | Where | When |
|---|---|---|
| VAPX.L (Asia-Pacific ex Japan) carries an estimated volatility of about 26% before calibration (30% after), well above the region's usual 15–20%, so its risk contribution is 3.5% for 1.4% of the value. It may be a price-data problem (it is quoted in dollars) | `backend/data`, the price cache | Investigate |
| Registry entries marked "Corrected Sep 2026 from knowledge of the LSE listing" should be checked against the issuers' factsheets. Two links were wrong; others may be | `backend/data/uk_etf_registry.json` | Data check |
| The portfolio list fetches each portfolio's full history to draw its trend line: one request per row. Fine for a handful; with many portfolios, add a short trend to `/portfolios/user/{id}` or load it as rows scroll into view | `routes/portfolio/PortfoliosPage.tsx` | When lists grow |
| An archived portfolio still accepts money and rebalances. Archiving only takes it off the list | `backend/api/routes` | If archived should mean closed |
| axe covers what can be checked automatically. No one has yet been through the journey with a screen reader (NVDA, VoiceOver) | the whole app | Before release |
| Heatmap shading uses `color-mix()` (Chrome 111, Safari 16.2, Firefox 113). Older browsers show the cells unshaded, with every figure still printed | `charts/Heatmap.tsx` | Acceptable |
| The onboarding walk-through unit test can pass five seconds under a full parallel run; it passed on rerun | `routes/start/start.test.tsx` | Watch |
| Without a risk profile in this browser, the outlook starts at 10 years rather than the investor's own horizon | `routes/portfolio/outlook` | Acceptable; the box can be changed |
| Local test data: user "Phase Three", its risk profiles and portfolio 20 were created while checking the journey against the real API | local database | Delete if unwanted |
| All 19 older local portfolios predate snapshots and the ledger replay, so construction and history are empty for them | local database | Open a new portfolio to see both |

Resolved in Phase 5:
- no way to archive a portfolio;
- no dark theme;
- a scrolling table that the keyboard could not reach;
- the unexplained difference between Performance's return and gain.

Resolved in Phase 4:
- matching users by name;
- `palette.sleeveOf` duplicating `policy.sleeve_of`;
- the style guide's holdings table scrolling sideways on phones;
- the portfolio page being an overview only.

Resolved in Phase 3:
- the builder creating a portfolio on every visit;
- onboarding inventing a profile when the API failed;
- the autofocus that skipped the skip link;
- the 931 kB bundle;
- the legacy client and store.

## 10. After the overhaul

The five phases are done, and section 13 covers the plain-terms pass after them. Worth doing next:
- a screen-reader pass through the whole journey;
- the VAPX.L and registry data checks above;
- the Figma steps below, once there is an editor seat.

## 11. Figma

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

## 12. Contract samples

`frontend/src/test/contract/*.json` are responses recorded from the running API.
`src/api/contract.test.ts` parses each one with the schema the app uses, so a backend change
that breaks the client fails in CI rather than in the browser. After changing a response model,
start the API (`make backend`) and record again:

| File | Request |
|---|---|
| `preview.json` | `POST /api/portfolio/preview` for user 1, risk 9 (capped to 7), £50,000 |
| `construction.json` | `snapshot_from_result(build_optimised_portfolio(7, 1.0), 7)` wrapped in `ConstructionResponse` (no local portfolio has one yet) |
| `construction-legacy.json`, `history-legacy.json` | `GET /api/portfolio/19/construction`, `GET /api/portfolio/19/history` |
| `universe.json` | `GET /api/universe?portfolio_id=19`, with SGLP.L's factsheet link cleared by hand after the registry fix |
| `track-record.json` | `GET /api/strategy/track-record?risk=5`; `benchmark_funds` was added by hand when the field was introduced, matching what the API now serves |
| `monte-carlo.json` | `POST /api/monte-carlo` with £50,000, £250 a month, 15 years, 500 paths, `annual_return` 0.065, `annual_volatility` 0.089, `goal_amount` 150,000 and `real_terms: true`. The contract test checks that paid-in counts each payment at face value. |
| `portfolios.json`, `risk-profile.json` | `GET /api/portfolios/user/1` (the first two rows; recorded again after `archived_at` was added), `GET /api/risk-profile/1` |

## 13. Plain terms, explanations and portfolio statistics

A pass after Phase 5, from review of the running app: some phrases were vague, the outlook spoke in
"1 in 10" odds, the track record's comparison was unnamed, and the portfolio had no technical figures.

### Terms

| Before | After |
|---|---|
| Today's money / pounds of the day | Adjusted for inflation / not adjusted for inflation |
| Middle outcome | Median (value, projection) |
| 8 in 10 outcomes, middle half of outcomes | 80% probability range, 50% probability range |
| Best 1 in 10 above … worst 1 in 10 below | 10% probability above … 10% probability below; 90th … 10th percentile in tables |
| Chance of ending below what was paid in | Probability of a loss (ending below the amount paid in) |
| Typical yearly swing (±) | Volatility (standard deviation of yearly returns) |
| Share of the risk / of the money | Risk contribution / share of value |
| Return since opening, return, time-weighted | Time-weighted return |
| A year, on average; realised so far | Annualised return |
| Worst fall from a high | Maximum drawdown |
| On its cost / added to return | Return on cost / contribution to return (pp) |
| Fund costs | Ongoing charges |
| These rules / two-fund portfolio | This strategy (backtest) / Benchmark: 50% VWRL.L + 50% AGBP.L |

- **Charges.** The outlook and proposal notes said "Before fund costs". The expected returns are
  net of each fund's charge (deducted from the equilibrium prior; trailing prices are already net),
  so they now say "After fund charges".
- **Why "backtest", not "projected".** The track record is the construction run on past prices,
  deciding each date with only what was known then. It is history simulated, not a projection, so
  the line is "This strategy (backtest)". The projection is the outlook's fan.

### Explanations on hover, tap and focus

- `lib/glossary.ts` holds one definition per term, so a term means the same thing everywhere.
- `ui/Term.tsx` underlines a term with dots. Hover, tap or Tab opens its explanation; Escape and
  leaving close it. The explanation is the term's accessible description and is hidden from the
  reading order, so it is announced once.
- `ChoiceGroup` options take a `tip`, shown beside the option (so clicking it never picks it) and
  read as the radio's description. The inflation choice uses it.
- Tips are fixed to the screen and placed by `placeTip`: lined up with the term, below it or above
  it in the lower part of the screen, never past an edge.
- **Found in the screenshots.** The `.stagger` entrance animation (`animation: … both`) leaves a
  transform on each section, which makes `position: fixed` measure from the section, not the
  screen: tips opened 150px from their term. They are now rendered into `document.body` through a
  portal, and `e2e/workspace.spec.ts` checks a tip opens beside its term, inside the screen, and
  stays open under the pointer. The test fails without the portal.
- Tips follow their term while the page scrolls or resizes, rather than closing: Tab scrolls an
  off-screen term into view, which would otherwise shut the tip it had just opened.
- Terms stay out of table headers. On a phone a stacked table hides its header row, so a focusable
  term there would be a tab stop no one can see; the holding-gains terms are explained in the
  paragraph above the table instead.

### Portfolio statistics

A column beside the holdings on the Overview (`routes/portfolio/overview`), stacking beneath them
below 1000px. Each label is a `Term`.

| Figure | How |
|---|---|
| Expected return | Σ wᵢμᵢ, the snapshot's net-of-charges estimates |
| Volatility | √(w′Σw), Σ from the snapshot's volatilities (already ×1.15) and correlations |
| Sharpe ratio | (expected return − risk-free) ÷ volatility, against the snapshot's rate |
| Value at risk (95%, 1 year) | max(0, 1.645σ − μ), as a share and in pounds of today's value; normal returns, so it understates fat tails |
| Diversification ratio | Σ wᵢσᵢ ÷ σₚ |
| Effective number of holdings | 1 ÷ Σ wᵢ² |
| Ongoing charges | Σ wᵢ × charge, and in pounds a year |
| Time-weighted return, annualised return, maximum drawdown | From the ledger replay, as on Performance |
| Realised volatility | Sample standard deviation of daily index returns × √252, from 20 returns (21 days of values) |

- The weights are what each fund is worth today when every fund has a price, otherwise the
  targets; the column says which. At the target weights the figures reproduce the snapshot's
  stored ones (6.50%, 8.95%, 0.254 in the contract sample).
- `routes/portfolio/covariance.ts` builds Σ once for these and for the Universe page's risk
  contributions.
- The track-record API now returns `benchmark_funds` (ticker, registry name, weight), from
  `benchmark_mix` in `backend/eval/track_record.py`, which the backtest script also uses. The
  names come from today's code while the series were built earlier, so a test checks that each
  level's funds still match the committed artefact's label; rebuild the artefact if they part.

### Tests

At the end of this pass:
- 615 unit tests, covering 99.7% of statements and 95.3% of branches;
- 74 browser checks, axe clean in both themes;
- 175 backend tests.
