---
name: political-campaign-commercial-proposal
description: Use this skill when the user needs to generate a non-technical commercial PDF proposal for a software system using an expert council, real application screenshots, and Chrome headless A4 rendering. It is especially useful for proposals aimed at political candidates, campaign managers, executives, or buyers who care about control, decision-making, implementation, and business value rather than technical architecture.
---

# Political Campaign Commercial Proposal

## Objective

Generate a persuasive, non-technical commercial PDF proposal for a software system using a council of expert agents, real screenshots from the application, and an HTML/CSS layout rendered to A4 PDF with Chrome headless.

The proposal must sell control, decision-making, operational visibility, and campaign impact. It must avoid technical over-explanation and must not exaggerate features beyond what the system actually does. It should feel like an extension of the product: reuse the application's own visual identity (primary color, typography, card style) so the proposal looks native to the system.

## When To Use

Use this skill when the user asks to create, improve, review, or regenerate a commercial proposal PDF for a software platform, especially when:

- The buyer is a political candidate, campaign manager, party, government team, or executive decision-maker.
- The proposal needs real screenshots from the application.
- The final artifact is HTML/CSS rendered to PDF.
- The content must be commercial, strategic, and non-technical.
- Multiple expert perspectives are needed before writing or designing the proposal.

## Council Roles

Use the following expert council (dispatch as parallel agents where independent; each writes its determination to a file for the copywriter/designer to consume):

1. **Proposal Director** — Owns the narrative, resolves conflicts, decides section order and length budget, keeps the proposal focused on the buyer's main reason to buy.
2. **Browser Screenshot Capturer** — Uses the app through a headed browser and captures real screens. Screenshots must be complete, clean, relevant, and free of permission popups, browser clutter, broken states, or excessive blank space.
3. **Functional Verifier (Programmer)** — Checks the actual software behavior and prevents exaggerated or false claims. Validates what the platform truly does; provides a "claims to avoid" list.
4. **Political Strategist (message & positioning)** — Explains what each screen helps the candidate decide; converts features into control, message adjustment, and risk detection.
5. **Second Political Strategist (field, territory & mobilization)** — Focuses on ground game: where to send brigades, coverage gaps, GOTV / "sacar el voto", territorial competition. Complements role 4.
6. **Marketing Expert** — Owns the emotional hook and brand appeal so the proposal "charms and enchants": headline, tone, promise, and the way value is dramatized for a non-expert buyer.
7. **Commercial Strategist (Sales)** — Defines the main sales argument, differentiators, objections, closing angle, implementation framing, and buyer value.
8. **Implementation Analyst** — Defines onboarding, required inputs, adoption risks, training, support, timelines, and pilot options.
9. **PDF Editorial Designer** — Designs the A4 layout, visual hierarchy, typography, page rhythm, section balance, screenshot sizing, and print-readability; enforces the length budget.
10. **Copywriter** — Writes concise, persuasive, non-technical copy in the buyer's language.
11. **Reviewer** — Final checks for accuracy, clarity, spelling, layout defects, orphan blocks, repeated ideas, and weak pages.

## Default Priorities

For political campaign software, prioritize the message in this order:

1. **Control of the campaign** — the buyer must immediately understand how the system gives visibility, order, and command.
2. **Decisions that help win** — every module must connect to a practical campaign decision.
3. **Territorial and electoral visibility** — maps, dashboards, and heatmaps sell the ability to read the terrain in real time.
4. **Operational discipline** — how the platform organizes teams, tasks, evidence, progress, and accountability.
5. **Speed of reaction** — how the campaign detects risks and responds fast.

The first page must communicate the core promise before showing module detail.

## Process (phases)

1. **Brief** — Proposal Director sets buyer, context, main promise, tone, length budget, and what to include (pilot, plans, implementation).
2. **Functional inventory** — Verifier lists real modules, screens, data, actions, limits, allowed vs forbidden claims.
3. **Screenshot capture** — Capturer produces clean, full screens (no popups/whitespace); saves with clear names and a manifest.
4. **Political value map** — both strategists map each module to: what it shows, how it works, what decision it enables, why it matters.
5. **Commercial architecture** — Sales + Marketing order the sections for selling and set the hook.
6. **Copy draft** — Copywriter writes non-technical, benefit-first, tied to control/decisions.
7. **PDF design** — Designer builds/updates a single self-contained HTML with the product's visual identity; enforces the length budget and page-break discipline.
8. **Accuracy review** — Verifier confirms every claim matches the app.
9. **Commercial review** — Sales/Marketing/Political confirm it sells and closes.
10. **Render & visual QA** — render with Chrome headless A4, then inspect page by page against the checklist.

### Disagreement rules
- Commercial vs technical → functional truth wins.
- Design vs message → sales clarity wins.
- Political vs commercial → Proposal Director decides via: "Does this help the candidate understand how they gain more control?"
- If a section does not add control, decision, or close → cut it.

## Conventions

- Generic unless the user provides a brand; never invent client/candidate/campaign names, metrics, integrations, or case studies. Neutralize tenant branding before capturing (set a generic brand name).
- Commercial language, not documentation. No stack/architecture jargon.
- **Match the product's visual identity**: pull the real primary color, fonts, card radius, and shadows from the app's stylesheet so the PDF reads as an extension of the system.
- Respect the requested **length budget** (e.g., "max 5 pages"): if content exceeds it, cut or condense — do not overflow.
- Screenshots must be full and clean: no permission prompts (grant geolocation / dismiss "activate location" on maps), no cookie banners, broken/loading states, dev overlays, or excessive blank space. Auto-trim white borders; keep maps' legends visible so the reader understands what the map means.
- Render the final PDF from HTML/CSS with Chrome headless A4:
  `"/path/to/Chrome" --headless=new --disable-gpu --no-pdf-header-footer --print-to-pdf=out.pdf --virtual-time-budget=20000 --run-all-compositor-stages-before-draw "file://.../index.html"`
- Each featured module should convey: what it shows · how it works · what decision it enables · why it matters.
- Do not let visual design hide weak content; do not let technical accuracy weaken the commercial message.

## Visual Review Checklist

- [ ] Page 1 clearly sells campaign **control**; value graspable in under 2 minutes.
- [ ] Every screenshot is real, clean, relevant; no permission popups/overlays; no large blank regions.
- [ ] Maps show their legend so the reader understands what pins/colors mean.
- [ ] Every featured module: shows something, explains how it works, connects to a decision.
- [ ] No "Qué aporta"/benefit block orphaned on an almost-empty page.
- [ ] Figures of different heights are visually balanced; captions stay with their image.
- [ ] Headings not stranded at the bottom; no text overlap; no clipped/broken images.
- [ ] Page breaks intentional; typography, margins, colors consistent with the product.
- [ ] Within the length budget (e.g., ≤ 5 pages).
- [ ] Non-technical throughout; all claims verified against the real system.
- [ ] Ends with a clear next step (demo, pilot, meeting).
```
