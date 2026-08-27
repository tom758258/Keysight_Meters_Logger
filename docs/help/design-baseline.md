# Help Design Baseline

## 1. Purpose

This document records the information architecture, editorial style,
support-boundary writing patterns, terminology style, and presentation traits
observed in the current Meters Tool user-facing documentation. It is a
developer/maintainer reference that informed the shared Help presentation
layer later implemented in the repository. This document is a historical design
baseline recording the state observed before the shared Help implementation
was completed; references to the legacy presentation describe the state
observed when the baseline was created.

- The Markdown USER_GUIDE and Supported Models files are the content sources.
- The legacy Traditional Chinese HTML mirrors were presentation references
  only; their body text is not authoritative content.
- This baseline does not itself define the future template implementation,
  generator, packaging, or application integration.

It is not a user guide and does not change any user-facing documentation.

## 2. Source Material

Content sources:

- `docs/cli/USER_GUIDE.md`
- `docs/cli/USER_GUIDE.zh-TW.md`
- `docs/webui/USER_GUIDE.md`
- `docs/webui/USER_GUIDE.zh-TW.md`

Historical presentation references:

- the former CLI Traditional Chinese USER_GUIDE HTML mirror
- the former WebUI Traditional Chinese USER_GUIDE HTML mirror

These mirrors were removed after the shared Help presentation and generated
runtime Help replaced them.

Shared Product support authority:

- `docs/core/supported-models.md`
- `docs/core/supported-models.zh-TW.md`

Supported Models is the shared user-facing authority for exact Product-open
support scope, and both guides link to it. It is not the source of CLI/WebUI
editorial or visual style. Legacy HTML bodies were separately maintained and
had drifted from the current Markdown guides, so only their presentation
traits are evidence here, never their wording.

## 3. Shared Information Architecture

Both guides follow an operator journey rather than a component or module
inventory:

- An opening paragraph introduces audience and purpose before detailed
  settings.
- Startup or entry instructions appear early.
- A first-use / first-live workflow appears before advanced detail, with
  new setups kept bounded or otherwise operator-controlled while they are
  validated.
- Support boundaries are explained near the workflows they affect.
- Organization is workflow-oriented, not organized by code or implementation
  module.
- Troubleshooting appears late, followed by shared support references.
- Supported Models serves as the shared Product support authority for both
  guides.
- Exact Product support is never inferred from mere resource discovery;
  discovery results always defer to the Supported Models scope.

Current section names, counts, and order are evidence of this design pattern,
not a frozen template contract.

## 4. CLI-Specific Information Architecture

The current CLI guide is an operator workflow guide, not a complete CLI
reference. Its flow moves from starting the executable through a first live
run (discovery, explicit resource selection, one bounded immediate-mode
sample), live support scope reminders, choosing measurements and trigger
modes, common settings, CSV output checks, stop paths, and troubleshooting.

Observed documentation boundary:

- Exact CLI options, accepted values, ranges, and defaults are delegated to
  `meters-tool <command> --help`.
- Exact Product-open support scope is delegated to Supported Models.

Normal Product guidance stays System-VISA-oriented: the guide states that the
CLI uses the computer's System VISA runtime by default and that backend
selection neither changes nor expands Product support. It does not teach
optional backend setup.

This flow describes the current operator journey; it is not a required
template section list.

## 5. WebUI-Specific Information Architecture

The WebUI guide documents user-visible screens and workflows rather than
backend/API structure. Its current flow covers startup through the launcher,
the browser/operator workflow, a screen overview tied to named panels,
measurement and trigger configuration, status/live data behavior, CSV output,
stop/exit behavior, troubleshooting, operator safety notes, and a shared
dependency on Supported Models for exact support scope.

Recurring traits:

- startup;
- browser/operator workflow;
- screen overview tied to named panels;
- measurement/trigger configuration guidance;
- status/live data description;
- troubleshooting;
- shared Supported Models dependency.

Desktop reuses the WebUI operator journey and does not introduce a separate
user-guide architecture.

No future `/help/` implementation details belong in this section.

## 6. Editorial Style

Observed consistently across both guides:

- operator-facing language;
- workflow-first organization;
- concrete procedural steps with copyable commands or screen actions;
- safety-aware sequencing (concurrent-control warning before live runs;
  terminal and wiring confirmation before current or 4-wire measurements);
- explicit boundary statements about what a result proves and does not prove;
- examples accompanied by context and expected results;
- live, dry-run, and simulator/simulate modes kept distinct where relevant;
- unsupported combinations described as failing closed rather than silently
  enabled;
- no marketing language;
- no developer setup or implementation tutorial inside USER_GUIDEs; the
  WebUI guide explicitly avoids developer details, and the CLI guide
  delegates its option inventory to command help.

Risky actions appear after the conditions that make them safe.

## 7. Support-Boundary Writing Patterns

Boundaries both guides repeatedly express:

- A resource answering `*IDN?` or appearing in `list-resources` output is not
  by itself proof of Product-open support.
- Explicit model selection (CLI `--model`, WebUI `Expected model`) is an
  expected-model guard/planning input; it does not unlock another support
  scope, and a mismatch fails before instrument setup.
- Unsupported model, transport, backend, measurement, or trigger combinations
  fail closed.
- Optional backend scope does not expand unsupported Product scope; the
  standalone CLI executable supports the fixed System VISA path only.
- Supported Models is the shared source of truth for exact Product-open
  scope.
- The WebUI exposes no backend selector, and its scan/run paths accept no
  backend override.
- Normal CLI operation uses System VISA when the advanced backend option is
  left unset.

These patterns describe how boundaries should remain communicable; this
baseline adds no backend setup instructions and does not teach optional
backend syntax.

## 8. Technical Terminology Style

Traditional Chinese prose retains established technical terms where this aids
precision and cross-document consistency. Observed examples include:
Product, Product-open, backend, profile, workflow, live, dry-run, simulator,
System VISA, WebUI, CLI, Auto Range, Auto Zero, NPLC, DCV Ratio, transport,
expected-model guard, planning model, and Core policy.

zh-TW text often pairs a Chinese rendering with the English term in
parentheses on first use (for example 自動量程（Auto range）or 立即模式
(immediate mode)) and then continues with whichever form reads naturally.

Machine-facing identifiers remain unchanged: model IDs, stable model IDs,
measurement IDs, trigger mode IDs, CLI flags, environment variable names,
VISA resource strings, numeric limits, units, and file formats such as CSV.

Neither direction is absolute: not every English technical word is retained,
and retained terms are not all translated. A future Help presentation must
render this mixed style faithfully without rewriting machine-facing
identifiers.

## 9. Existing Visual Baseline

At baseline time, both legacy HTML files shared:

- a light-oriented reading layout on a white body;
- a sticky left sidebar table of contents on desktop, about 280 px wide, on a
  light slate background with a right border;
- a bounded main reading column around 900 px max-width;
- a system UI font stack including `Noto Sans TC`, line-height about 1.7;
- a blue primary accent used for links and active TOC entries;
- neutral slate-style backgrounds, text, and borders;
- a clear h1/h2 hierarchy; the WebUI file additionally styles content-level
  h3 headings while the CLI file does not;
- an h2 separator rule (bottom border) with scroll margin for anchor jumps;
- dark rounded code blocks with light text;
- light inline-code treatment on a light slate background;
- a copy button positioned at the top-right corner of each code block;
- responsive stacking at about 768 px, where the sidebar becomes a top block
  above the content.

Observed differences:

- Only the WebUI legacy file provides content h3 styling; the CLI legacy
  file has no equivalent rule.
- Neither legacy TOC includes h3 entries even though the WebUI body uses h3
  subheadings under troubleshooting.
- Body-content drift differs per file (see section 11); the visual shell
  itself is otherwise effectively identical across the two files.

Known content requirements for the future shared presentation (not observed
shared legacy traits): Supported Models contains h3 sections and wide tables
whose cells include inline code. The future presentation must render these
readably. Neither legacy USER_GUIDE page demonstrates wide-table
presentation, and only the WebUI legacy page demonstrates content-level h3
styling.

None of these values are permanent design tokens or test contracts; they are
current implementation references to unify deliberately in the shared Help
presentation.

## 10. Existing Interaction Baseline

Both legacy files implemented identical inline behavior:

- automatic TOC generation into the sidebar from document headings;
- anchor navigation using generated heading IDs;
- active-section indication during scrolling using IntersectionObserver;
- copy buttons on code blocks with localized success feedback; copy failures
  are logged to the console;
- responsive layout behavior that stacks the sidebar above the content on
  narrow viewports.

Limitations recorded at baseline time:

- The generated TOC is based on h2 entries only, in both files.
- Future Supported Models pages need heading support below h2 because that
  document uses h3 sections.
- Copy success is visible today; failure feedback is console-only.

Do not treat the current inline script structure, exact observer options, or
specific DOM query details as contracts. The future JavaScript architecture
is a separate decision.

## 11. Baseline-Time Gaps / Future Decisions

Gaps recorded when this baseline was created:

- No shared Help template exists yet; the two legacy HTML files are separate
  hand-maintained copies.
- No shared Help stylesheet exists yet.
- No Markdown-to-Help HTML generator exists yet.
- Legacy HTML bodies are separately maintained and stale relative to the
  current Markdown: the legacy CLI page still carries older backend-option
  wording removed from the current guide, references anchors outside the
  guide, and both legacy pages link to raw `.md` targets instead of Help
  pages.
- Supported Models requires readable wide-table presentation and consistent
  h3 support; wide-table presentation is not demonstrated by the legacy
  USER_GUIDEs, and h3 styling currently exists only in the WebUI legacy
  page.
- Help packaging and application integration are not implemented yet.
- Help language chrome will need EN / zh-TW values later.

Dark mode, theme switching, search, breadcrumbs, version selection, Help
routing, packaging layout, and Markdown library choice are separate future
decisions and are not settled here.

## 12. Preserve vs. Do Not Freeze

### Preserve

- Markdown as the content source of truth.
- Operator-facing, workflow-first organization.
- Clear Product support boundaries next to relevant workflows.
- Supported Models as the shared Product support authority.
- Readable TOC and anchor navigation.
- Clear heading hierarchy.
- Readable code blocks and inline code.
- Code-copy usability.
- Responsive reading layout.
- Readable wide-table behavior.
- Offline-friendly presentation.
- EN / zh-TW content parity.

### Do Not Freeze

- Exact pixel dimensions.
- Exact color hex values.
- Exact CSS selector structure.
- Exact DOM markup.
- Exact JavaScript implementation.
- Exact IntersectionObserver settings.
- Exact section count, names, or order.
- Current legacy HTML body content.
- Current stale legacy links.
- Exact current wording.
