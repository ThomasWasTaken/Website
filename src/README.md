# Website Repository Structure

This repository has two main concerns:

- `assets/pages/`: frontend HTML pages for the legal demo.
- `django/legal_backend/`: backend API for event tracking and analytics summary.

## Key Navigation Entry Points

- `index.html` -> redirects to `assets/pages/legal_site.html`
- `assets/pages/legal_site.html` -> non-tracked overview and dashboard shell
- `assets/pages/legal_site_agentveiw.html` -> tracked legal agent view hub

## Tracking Scope

Tracking is intentionally restricted in the backend to these page identifiers:

- `legal_site_agentveiw`
- `forside`
- `testamente`
- `ægtepagt`
- `samejeoverenskomst`
- `fuldmagt`
- `juridisk-konsultation`
- `lejekontrakt`

This prevents accidental tracking from `legal_site.html` and the technical deep-dive pages.

## Suggested Conventions

- Keep all legal frontend pages in `assets/pages/`.
- Keep tracking-only logic in `assets/pages/legal-agent-shared.js`.
- Keep backend aggregation logic in `django/legal_backend/tracking/views.py`.
