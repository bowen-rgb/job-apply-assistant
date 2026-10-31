# Project guidance

## UI design references

For future UI work, consult [docs/UI_DESIGN_REFERENCES.md](docs/UI_DESIGN_REFERENCES.md) and the user-requested Refactoring UI skill linked there before changing visual design. Preserve this project's existing plain HTML/JavaScript/CSS architecture and design tokens; do not add Tailwind or replace the design system just to match examples. This reference supplements the user's existing visual direction and beginner-friendly workflow requirements.

## Motivation letters

Before changing letter generation, read [docs/LETTER_QUALITY_RULES.md](docs/LETTER_QUALITY_RULES.md). Keep rules generic and candidate-scoped; never embed a particular candidate's facts in shared prompts. User CVs, notes, drafts and application material belong in ignored candidate data, not Git.

## Target interface

New UI work targets the desktop browser Dashboard. The user has no current mobile-interface plans; do not spend time adding mobile layouts or dedicated mobile checks unless explicitly requested. Preserve existing behavior.
