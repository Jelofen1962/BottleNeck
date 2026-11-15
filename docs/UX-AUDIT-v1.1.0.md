# BottleNeck UX audit, v1.1.0

Review date: 15 November 2026  
Scope: `index.html`, `static/styles.css`, `static/design-system.css`, `static/app.js`, generated interface patterns and release documentation.

## Findings and changes

| Area | Finding | Change in 1.1.0 |
|---|---|---|
| Version and cache labels | The authentication screen and static asset URLs did not consistently identify the active release. | Aligned the HTML title, footer, CSS/JS cache keys, Python version and package metadata to 1.1.0. |
| Color usage | Page modules had many one-off color literals and slightly different shades for similar states. | Centralized component color references in a shared token palette; raw hex literals no longer appear in component selectors. |
| Text sizing | Several compact labels fell below a comfortable reading size. | Raised small CSS text declarations to a 10.5px floor and replaced an 8px inline task caption. |
| Buttons | Browser defaults could make buttons inside forms submit unintentionally; generated controls needed the same rule. | Added explicit static button types and a dynamic normalizer that handles both inserted containers and inserted button nodes. |
| Native dialogs | Remaining browser prompts and confirmations interrupted the product flow and could not follow BottleNeck styling. | Routed text input and confirmation flows through the shared modal component with validation and cancel behavior. |
| Modal keyboard access | The main modal had partial focus handling; the tour and creator popup did not share the same focus lifecycle. | Added focus entry, focus trapping, inert background, Escape handling and focus restoration to all three overlays. |
| Navigation and tabs | The active navigation item and authentication tabs relied on visual classes alone. | Added `aria-current`, tab roles, selected state, panel relationships and keyboard focus behavior. |
| Chat controls | Several icon-only composer actions had no accessible name. | Added explicit labels; success, warning and error feedback now use distinct notification tones. |
| Responsive scale | A later token declaration could override the original sidebar width breakpoints. | Re-stated the responsive sidebar and 100% small-screen zoom rules after the design-system tokens. |
| No-op handlers | Empty event handlers added noise without behavior. | Removed empty listeners and added the pattern to the UI audit. |
| Form labels and dialogs | Autofocus selectors could choose the close button before a requested input; empty states used a line break as layout. | Autofocus now takes precedence; empty states use a titled paragraph structure. |
| Mobile navigation | The drawer had no explicit backdrop lifecycle and could leave focus on off-screen navigation after it closed. | Added a click-to-dismiss backdrop, inert/hidden state, Escape handling, focus trapping and page-heading focus after navigation. |

| Viewport review | Phone navigation actions crowded the breadcrumb; tablet and compact-desktop widths could overflow the top bar. | Added measured compact top-bar layouts at 320–1300px, retained usable search, moved workspace switching into the mobile drawer on phones, and verified no top-bar overflow at 17 widths. |
| Dialog sizing | Long task forms exceeded the usable viewport after 120% desktop zoom. | Added zoom-aware desktop dialog caps and viewport-bounded mobile dialogs with internal scrolling. |
| Mobile chat | The desktop message-feed minimum pushed the composer below the phone viewport. | Made the mobile chat a viewport-bounded flex layout, kept the message feed internally scrollable and moved the online roster above the conversation. |
| Role color | The default custom-role pill used the creator violet outside the creator signature. | Changed the default role color to a neutral graphite token; existing default-colored rows migrate to the neutral value. |

| Role and toast treatments | Custom role colors were not consistently reflected by role pills, while notification variants shared one surface. | Role pills now use validated role-color tokens; success, warning and error toasts have separate surfaces and icons. |
| Authentication controls | Tabs had visual selection state but no arrow-key navigation. | Added RTL-aware left/right navigation plus Home and End behavior. |
| Chat semantics | Message feed and @mention suggestions lacked clear assistive-technology relationships. | Added a labelled message region and listbox/option semantics for mention suggestions. |

## Design-system decisions

`static/design-system.css` now provides the last-mile rules for shared controls, headings, fields, panels, dialogs, chat, Markdown, toasts and focus states. `static/styles.css` retains page-specific layout rules and responsive compositions; it has not been flattened into one enormous stylesheet because doing so would make the page-level rules harder to maintain.

All text declarations in the two CSS files now meet the 10.5px CSS floor. The empty-state helper emits an icon, title and descriptive paragraph, and toast variants share the same layout while using distinct semantic tones. The interface continues to use Vazirmatn and Roboto, with the requested 120% desktop zoom and a reset at narrower widths.

## Browser review and responsive checks

A controlled Chromium review exercised the application shell with the real HTML, CSS and JavaScript, while the API calls reached a local FastAPI instance. The review opened all 18 primary views: overview, personal tasks, all tasks, Kanban, calendar, projects, teams, activity, reports, approvals, recurring tasks, templates, shared board, shared drive, shared notes, team chat, handbook and settings. No uncaught browser JavaScript errors appeared during that pass.

The top bar was measured at 17 viewport widths from 320px through 1440px. It did not create horizontal overflow at any tested width. A second pass checked eight key views at 390px; the document, body and main content stayed within the viewport. The mobile chat was checked at 390×844: the channel rail, online roster, conversation and composer all fit inside the viewport-bound layout. The task dialog was checked at 390×844 and at 1440×1000 with the requested 120% desktop scale. Both dialogs scroll internally, Escape closes them, and the desktop test confirmed focus restoration.

The browser harness substituted lightweight stubs for third-party CDN libraries (Lucide, Marked and DOMPurify) and for the WebSocket transport. It therefore validates BottleNeck's layout and application event flow, but it does not certify the third-party icon artwork, the production Markdown sanitizer build, or live WebSocket delivery. The server and API have their own integration tests; an actual Windows browser pass, real mobile-device test and independent accessibility/security assessments remain release follow-ups.

## What the audit cannot promise

No finite checklist can guarantee that nobody will encounter a UX defect. This pass fixes the issues it found and adds repeatable checks for the design rules that matter most: naming, focus, viewport fit, typography, colors, dialog behavior and mobile navigation. It does not replace testing with real teams and real content.

Future contributors must run `python scripts/ui_audit.py`, `uv run --group dev --python 3.12 pytest -q`, and follow `docs/UI-DESIGN-SYSTEM.md` whenever they add a page or component. A manual review must still cover long Persian and mixed-script content, keyboard-only use, reduced motion and an account with restricted permissions.
