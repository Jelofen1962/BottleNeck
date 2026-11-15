# Roadmap

`v1.0.0` marks the first stable public release for self-hosted use on a trusted private network. The roadmap below is a working list, not a promise of dates.

## Stable in v1.0.0

The current release includes task/project workflows, team chat, shared Markdown notes, concept boards, workspace files, role-based access, multiple workspaces, Jalali date presentation, live presence and a separate server operations CLI/GUI.

## Candidate work

| Area | Possible next work | Why it matters |
|---|---|---|
| Deployment | Container image, service templates and reverse-proxy recipes | Make repeatable installs easier to operate. |
| Storage | PostgreSQL support and storage abstraction | Support larger installations without sharing SQLite across hosts. |
| Operations | Better metrics, log retention controls and backup verification reports | Give owners a clearer view of server health. |
| Collaboration | Conflict-aware editing for shared notes and boards | Reduce accidental overwrites when several people edit at once. |
| Access | More granular resource policies and optional external identity providers | Fit teams with stricter account requirements. |
| Quality | Browser-based end-to-end tests and accessibility review | Catch interface regressions before release. |

## How priorities change

Issues with a clear reproduction, user impact and a proposed acceptance test are easier to prioritize. Add context to an existing issue before opening a duplicate; the maintainers will update this page when scope changes.
