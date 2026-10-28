<!--
  CLAUDE.md
  Project : Campaign Donations
  Date    : 2026-10-28
  Purpose : Standing instructions loaded by Claude Code sessions (CLI, desktop, cloud) working in this project.
  Changes :
    2026-10-28  Initial version generated from account preferences.
-->

# CLAUDE.md — campaign-donations

## Project
- Project name for comments and commits: **Morpheus**
- Hosted on the HopemanHorde website; repo is public with comments/issues limited to contributors/owner.

## Working rules (from Ward's account preferences)

### Data and research
- When asked for data of any kind, prefer facts backed by 3 or more sources and list those first; then present data or facts supported by fewer sources, marked as such.

### Identity and git
- Use the project name above in all comments, commit messages, issues and PRs for this project.
- All code lives in a git repository named after the project. If a new repo's visibility (public/private) was not specified, ask before creating it.
- Commit on the branch currently checked out; do not switch or rewrite branches others are working in.

### Development method
- Test Driven Design for all code: write or update the failing test first, then the implementation.
- Run linting checks (where a linter exists for the language) before every commit.
- Comment code blocks rather than individual lines; add a line comment only where a line contains a complex calculation.
- For new features in a larger project, use feature flags so incomplete features can ship disabled while the rest of the project releases.
- Use SemVer for all versioning (keep VERSION, package metadata and CHANGELOG.md in sync).

### Security and licensing
- Perform security checks on all code; address all OWASP high and medium concerns, with particular attention to third-party includes and dependencies.
- Use only open-source code and libraries licensed for private use or less restrictive.
- Credentials stay on the local machine only. Never commit, upload or publish credentials, tokens, keys or local config files that contain them (e.g. deploy.local.json, CREDENTIALS.txt). Use git credentials only from the local shell.

### Build and documentation
- The project must be buildable manually by Ward or others without Claude.
- Keep README.md plus the standard companion docs (CHANGELOG.md, CONTRIBUTING.md, LICENSE, setup/build notes as applicable) current.
- Follow standard industry directory layout for the project's language/stack.
- Every file starts with a header: purpose/usage (including parameters), project name, date, and a change log for medium-to-major changes after creation.
