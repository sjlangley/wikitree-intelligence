# Design System — WikiTree Intelligence

## Product Context
- **What this is:** A local-first genealogy workbench that imports a GEDCOM and helps a serious researcher reconcile people into WikiTree without creating duplicates.
- **Who it's for:** A power user doing long-session genealogy research, source comparison, and evidence-backed identity review.
- **Space/industry:** Genealogy software, family-tree research, archival record reconciliation.
- **Project type:** Hybrid. Marketing-style framing at the top level, then a dense task-focused app workspace.

## Aesthetic Direction
- **Direction:** Editorial Archive Workbench
- **Decoration level:** Intentional
- **Mood:** Calm, credible, source-aware, and human. The product should feel like a research desk with modern software discipline, not a nostalgic scrapbook and not a generic admin dashboard.
- **Reference sites:** FamilySearch, Geneanet, MyHeritage. We borrow their person-centric and evidence-heavy literacy, but reject their dated or overly busy visual defaults.

## Typography
- **Display/Hero:** Instrument Serif
  Gives the product gravity and memory without slipping into costume drama.
- **Body:** Source Sans 3
  Clear, plainspoken, and built for long reading sessions.
- **UI/Labels:** IBM Plex Sans
  Stronger technical voice for metadata labels, queue states, and navigation.
- **Data/Tables:** IBM Plex Sans
  Use tabular numerals for dates, counts, and score columns.
- **Code:** IBM Plex Mono
  Reserve for IDs, paths, packet references, and machine-shaped provenance.
- **Loading:** Google Fonts or a self-hosted equivalent before production hardening.
- **Scale:**
  - Hero: 72px
  - Display 1: 48px
  - Display 2: 36px
  - Section title: 28px
  - Body large: 20px
  - Body: 17px
  - Small: 14px
  - Micro label: 12px

## Color
- **Approach:** Restrained
- **Primary:** `#355C4B`
  Main action color, used for confirmation and steady forward motion.
- **Secondary:** `#2F5D7E`
  Linked-state and trusted relationship color, cooler and more technical than the primary accent.
- **Neutrals:** Warm archival range
  - Background: `#F4F0E8`
  - Surface: `#FBF8F2`
  - Surface alt: `#E9E2D6`
  - Divider: `#CFC4B3`
  - Primary text: `#1F2824`
  - Muted text: `#5F6B63`
- **Semantic:**
  - Success / confirmed: `#355C4B`
  - Info / linked: `#2F5D7E`
  - Warning / needs review: `#9C5A2E`
  - Error / conflict: `#8A3B32`
- **Dark mode:** Re-map surfaces rather than inverting them. Use dark olive-charcoal surfaces, off-white text, and reduce accent saturation slightly so the interface still feels archival instead of neon.

## Spacing
- **Base unit:** 8px
- **Density:** Comfortable-compact
- **Scale:** 2xs(4), xs(8), sm(12), md(16), lg(24), xl(32), 2xl(48), 3xl(64)

## Layout
- **Approach:** Hybrid
  Editorial framing for overview surfaces, then a disciplined split-pane workbench for the app itself.
- **Grid:** 
  - Mobile: single column
  - Tablet: 8-column
  - Desktop app workspace: left rail / main comparison pane / right evidence rail
- **Max content width:** 1380px for broad application surfaces, 760px max readable line length for prose-heavy areas.
- **Border radius:** sm: 6px, md: 12px, lg: 20px, pill: 999px

## Motion
- **Approach:** Minimal-functional
- **Easing:** enter(ease-out), exit(ease-in), move(ease-in-out)
- **Duration:** micro(80-120ms), short(150-220ms), medium(240-360ms), long(400-600ms)
- **Usage:** Motion should clarify state changes, queue transitions, and diff highlighting. No ornamental choreography.

## Component Principles
- Cards must earn their existence. Do not default to dashboard-card mosaics.
- The core screen is a workspace, not a marketing page. Favor rails, inspectors, comparison panes, and structured tables over stacks of generic panels.
- Evidence and provenance should always have a visible home.
- Status language should be specific and calm: "Needs review", "No safe match", "Connected", "Expired session".
- Keep side panels visually quieter than the central decision surface.

## Anti-Slop Rules
- No purple or indigo gradient defaults.
- No three-column feature grids with icons in colored circles.
- No centered-everything hero sections.
- No uniformly bubbly radius across every component.
- No decorative blobs, scrapbook flourishes, or fake heritage ornament.
- No generic SaaS copy patterns such as "unlock your family story" or "all-in-one solution".

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-04-07 | Initial design system created | Built from product context and category research on genealogy products |
| 2026-04-07 | Editorial Archive Workbench chosen | Best fit for evidence-heavy, duplicate-safe genealogy reconciliation |
| 2026-04-07 | Instrument Serif + Source Sans 3 + IBM Plex stack chosen | Balances archival warmth with modern research readability |
