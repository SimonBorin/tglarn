# Retrospective

This document is a living retrospective for the AI-Native Development Challenge. It will be updated as implementation progresses.

## AI Tools Used

- Codex: repository setup, structure planning, license review, documentation drafting, and command-line project operations.

## Development Workflow

Initial workflow:

1. Discussed project idea and constraints with the AI assistant.
2. Created a local git repository for `tglarn`.
3. Added GitHub remote for the fork.
4. Imported upstream ReLarn source into `vendor/relarn/`.
5. Reviewed upstream licensing and third-party notices.
6. Created top-level project documentation and challenge-required documents.
7. Kept original source, bot code, adapter code, deployment, docs, and tests separated by directory.

Planned workflow:

1. Define a minimal playable Telegram command loop.
2. Implement adapter code first, then Telegram handlers.
3. Add tests after each working slice.
4. Containerize with Podman.
5. Add GitLab CI.
6. Update this retrospective after each major iteration.

## What Worked Well

So far:

- AI was useful for quickly turning a broad idea into a concrete repository layout.
- AI helped identify license obligations beyond the main GPL license, including libfov and bundled Inconsolata font notices.
- Keeping `vendor/relarn/` separate from new code made licensing and architecture easier to reason about.
- The AI-assisted checklist approach helped avoid missing required challenge documents.

## What Did Not Work Well

So far:

- Writing outside the initial sandbox root required repeated permission escalations.
- Shell quoting around Markdown content with backticks was error-prone.
- The project direction changed while setup was already underway, so documentation needed to be realigned with the hackathon requirements.

## Surprises and Discoveries

- ReLarn contains more than just GPL-covered game code: `src/fov/` has a separate permissive license, and the bundled Inconsolata font uses the SIL Open Font License.
- The optional one-click GitLab/GitDocs bonus is not a natural fit for a Telegram bot unless the bot is hosted or a separate browser demo is created.
- The challenge documentation requirements are useful as architecture forcing functions, not just paperwork.

## Estimated Percentage of AI-Generated Code

Current estimate:

- New project scaffolding/docs: high AI assistance, roughly 80-90% drafted by AI and reviewed by the user.
- Imported ReLarn code: 0% AI-generated; third-party upstream source.
- Final application code: TBD after implementation.

This estimate will be revised before final submission.

## Time Spent

Current rough estimate:

- Repository setup and source import: 30-45 minutes.
- License review and notice setup: 30-45 minutes.
- Challenge documentation alignment: 30 minutes.

Implementation time: TBD.

## What I Would Do Differently Next Time

- Start from the challenge deliverables before creating project-specific docs.
- Create all required root documents in the first commit.
- Decide early whether the demo target is Telegram-hosted, local-only, or browser-playable.
- Use smaller file-writing steps when Markdown contains shell-sensitive characters.

## Key Lessons Learned

- AI works best here as a repository co-pilot when it continuously verifies the filesystem and git state.
- License review should happen before implementation, especially when adapting an existing game.
- A clear directory boundary between upstream code and new integration code reduces future maintenance risk.
- Retrospective notes should be captured during development, while the workflow issues are still fresh.
