# BottleNeck UI design system

Version: 1.1.0  
Last reviewed: 15 November 2026

This document defines the interface contract for every BottleNeck surface. It applies to the authentication flow, workspace navigation, task and project views, shared boards, drive and notes, chat, dialogs, server administration and future modules.

## Product rules

BottleNeck is a Persian-first workspace. A screen should answer three questions without making someone hunt: where am I, what can I do here, and what happens after I act? Keep the interface quiet enough for long work sessions, but give destructive actions and system errors enough weight to be noticed.

The product uses one visual language. A new feature must use the existing tokens and shared controls before adding its own styles. A page-specific exception needs a reason and a note in the relevant component CSS.

## Layout and spacing

Use the spacing scale `4, 8, 12, 16, 24, 32, 40`. Align controls to a common baseline and keep related fields close; separate unrelated sections with the larger steps. Avoid adding a new radius or shadow for a single component.

The desktop workspace retains the requested 120% scale. At widths of 900px and below, the scale returns to 100% and navigation moves to the compact layout. The top bar switches to a compact arrangement below 1300px; on phones, workspace switching stays in the navigation drawer while search remains available. Content must not require horizontal scrolling unless it is a naturally wide data view, such as a table or Markdown table.

Page headings use one title, an optional short explanation and actions that belong to that page. Keep one visually dominant primary action in a region. Secondary actions remain quiet; destructive actions use the danger treatment and require a clear confirmation when they remove data.

## Typography

Use Vazirmatn for Persian and Roboto for Latin text. Keep names, labels and explanatory copy in sentence case; reserve uppercase Latin overlines for short metadata only.

The CSS text-size floor is 10.5px. Desktop scaling raises the rendered size; do not work around the floor with inline styles. Page titles use the 23–34px responsive range, section titles use a consistent smaller scale, and body copy must retain enough line height for Persian diacritics and mixed-script text.

Use tabular numerals for counts and dates where alignment matters. Use `dir="ltr"` on technical identifiers, URLs, code, email addresses and phone numbers rather than reversing the entire component.

## Color and surfaces

All component colors come from the central token palette in `static/design-system.css`. Do not add raw hexadecimal values to component selectors. Add a token to `:root` when the product needs a new semantic color, then use that token everywhere.

The main workspace uses warm paper, white surfaces, graphite text and a restrained rust action color. Green communicates success, red communicates destructive or failed states, and amber communicates caution. Violet belongs to the Jelofen creator signature and must not become the general product accent.

Do not use decorative gradients, arbitrary colored borders, or emoji as interface icons. Use Lucide monoline icons with labels or accessible names.

## Controls and forms

Buttons must declare `type="button"` or `type="submit"`. Dynamically generated buttons pass through the button normalizer; icon-only buttons need an `aria-label` or a meaningful `title`.

Inputs need a visible label, a useful placeholder only as an example, and helper text when the accepted format or consequence is not obvious. Validation appears beside the field and explains how to fix the problem. Do not rely on color alone to communicate the state.

Use the shared `.primary-button`, `.secondary-button`, `.danger-button`, `.icon-button` and `.field` patterns. Don't create one-off button heights or field treatments without a documented need.

## Dialogs and popups

Use the shared in-app modal for prompts and confirmations. Native `prompt()`, `confirm()` and `alert()` dialogs are not allowed in application flows.

An open dialog must:

- Have `role="dialog"`, `aria-modal="true"` and an accessible title.
- Move keyboard focus inside when it opens and keep Tab navigation within the panel.
- Make the background inert while open.
- Close on Escape when it is safe to do so; unsaved Markdown changes must save or remain open.
- Restore focus to the control that opened it.

Only one modal layer should be active at a time. Confirm what will be removed, what will remain, and whether the operation can be undone. Long forms should scroll inside the dialog rather than push their actions off-screen. Dialog height must account for the desktop 120% zoom; test at 1440×900 and 1024×768 as well as phone sizes.

## Chat and live collaboration

Presence events must not clear a draft, reset a reply, or move the message feed unexpectedly. Keep the user's scroll position unless they were already at the bottom. Message actions should appear near the message they affect and use explicit accessible labels.

The composer keeps send, attachment, recording and resource-link actions visually distinct. Upload progress stays visible until the server confirms completion. Voice recording must show its active state and stop cleanly when the user leaves the chat view.

Use a clear hierarchy for sender, message, timestamp and reply context. Avoid placing every action permanently beside every message; reveal secondary controls on hover and keyboard focus.

## Feedback and empty states

Success, warning and error notifications use distinct tokenized tones and icon treatments. Announcements use `role="status"` for routine updates and `role="alert"` for errors. Toasts should describe the result, not the button the person clicked.

An empty state needs a specific title and a next step. Its description uses a paragraph, not a layout-dependent line break. Don't use filler text. Loading states should explain what is loading and disable duplicate submissions while an operation is in flight.

## Motion and accessibility

Keep transitions short and tied to a meaningful state change. Respect `prefers-reduced-motion`; never make information available only through animation. Maintain visible focus, semantic headings and landmarks, an accessible skip link, labels for controls and a sensible reading order in RTL. Authentication tabs support arrow keys, Home and End; the mobile navigation becomes inert while closed and traps focus while open.

## Responsive acceptance record

The v1.1.0 review measured the top bar at 17 widths (320, 360, 390, 560, 600, 650, 700, 760, 800, 900, 940, 980, 1000, 1100, 1200, 1280 and 1440px). No top-bar overlap or document-level horizontal overflow appeared in those samples. Chromium also opened the 18 main workspace views at desktop size and eight high-traffic views at 390px width; the document and main content stayed within the viewport during that pass.

The task dialog was checked at 120% desktop scale and at a 390×844 phone viewport. Both use internal scrolling, Escape closes the dialog, and the desktop pass restored focus to the invoking control. The phone chat was checked at 390×844 with the channel rail, online roster, conversation and composer visible in one bounded panel.

These are finite viewport and interaction samples, not a guarantee that every possible dataset or device will behave perfectly. Repeat the checks with long Persian labels, mixed LTR identifiers, a narrow 320px screen, a 1024×768 desktop and restricted workspace roles whenever shared layout rules change.

## Review checklist for every change

- Does the page use the shared title, spacing, color and control tokens?
- Can a keyboard user open, operate and close every control and dialog?
- Do all buttons have an explicit type and an accessible name when icon-only?
- Does a live update preserve typed text, focus and scroll position?
- Are errors actionable, and are empty states specific?
- Does the layout still work at 120% desktop zoom, compact desktop widths (980–1300px) and phone breakpoints (320–760px)? Is the chat composer visible without scrolling the whole page?
- Are Persian dates and mixed LTR identifiers readable?
- Did the UI audit and test suite pass?

Run `python scripts/ui_audit.py` before opening a pull request.
