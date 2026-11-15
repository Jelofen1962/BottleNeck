# BottleNeck changelog

## v0.9.0 · مدیریت سرور و جابه‌جایی داده

- افزودن CLI مستقل برای راه‌اندازی اولیه مدیر نصب، اجرای سرور، وضعیت، عیب‌یابی، لاگ، پشتیبان‌گیری، بازیابی، تنظیمات، کاربران، فضاها و مدیران سرور.
- افزودن پنل مستقل «مدیریت سرور» خارج از تنظیمات فضای کاری.
- افزودن نقش‌های سرور owner، operator و auditor با کنترل مجوز در سمت سرور.
- نمایش سلامت SQLite، بررسی foreign key، زمان روشن‌بودن، تعداد کاربران/فضاها/نشست‌ها، فضای مصرفی و آزاد و حجم لاگ.
- افزودن تنظیم میزبان/پورت و زمان‌بندی/نگهداری پشتیبان؛ تغییر میزبان/پورت پس از راه‌اندازی مجدد اعمال می‌شود.
- افزودن مدیریت مدیران سرور، خروجی کامل فضای کاری ZIP، خروجی CSV کارها/پروژه‌ها و ورود این داده‌ها از GUI.
- افزودن import/export کامل فضای کاری از CLI؛ بسته شامل داده‌ها و فایل‌های وابسته است و عمداً گذرواژه‌ها و نشست‌ها را صادر نمی‌کند.
- افزودن بازیابی آفلاین با تأیید دوگانه، بررسی مسیرهای ZIP، checksum، سلامت SQLite و پشتیبان پیش از بازیابی.
- افزودن مهاجرت خودکار از v0.8.x؛ سازنده قدیمی‌ترین فضای کاری به مدیر نصب اولیه تبدیل می‌شود.
- به‌روزرسانی cache-busting فایل‌های CSS/JS و مستندات نصب، CLI، GUI و بازیابی.

## v0.8.0 · Communication and knowledge editing

- Rebuilt shared Markdown notes into a split editor with a continuously updating, sanitized GFM preview, formatting toolbar, keyboard shortcuts, word count and autosave for existing notes. Saves are queued safely so edits made while a request is in flight are not silently discarded.
- Added chat message search across the current workspace/team channel, searching message text and sender names.
- Added @mention suggestions with team-aware filtering, server-validated recipients, in-app mention notifications and mention preservation when editing messages.
- Added chat replies with quoted context, message editing/deletion, and permission-aware moderation.
- Added chat media/file uploads with XHR progress reporting, a 25 MB per-file limit, an extension allowlist and permission-checked downloads.
- Added image previews, inline audio/video playback, and ordinary file download cards.
- Added voice-message recording through the browser MediaRecorder API, with a two-minute cap, upload progress and playback after sending. Microphone access on LAN devices requires HTTPS; localhost works as a secure browser context.
- Added resource cards linking to tasks, projects, concept boards, shared Markdown notes and shared files. Resource search only returns items visible to the current user.
- Added attachment staging cleanup after 24 hours, server-derived MIME types for safer inline media handling, chat attachment inclusion in backup archives, and channel-aware permission checks.
- Preserved the existing v0.7.0 identity/presence/role features, Persian RTL/Jalali UI, approximately 120% desktop scale, LAN port 1939 and Jelofen creator signature.

## v0.7.0 · Identity, roles and live team presence



- Added a Remember me option. Persistent sessions last 30 days; regular browser sessions use a session cookie and expire server-side after 12 hours. The chosen value is preserved across the TOTP challenge.
- Added optional profile image upload during registration and profile image management in settings. JPEG, PNG, WebP and GIF are limited to 3 MB and served only to authenticated workspace members.
- Added short workspace join codes: eight characters, 15-minute expiry, one use by default, configurable use limit, hashed storage and per-user attempt throttling. Existing accounts join without creating a duplicate account and keep their previous workspace memberships.
- Added named, color-coded custom roles with an explicit permission allow-list, plus backend enforcement for each supported permission.
- Expanded permission-aware UI controls and aligned the settings matrix with the API permission catalog.
- Added team presence roster with names, avatars, roles, active pages and named color cursors. Cursor positions are approximate viewport percentages; presence expires after 45 seconds.
- Improved chat into a channel/message/online-member layout and update the roster in place so presence refresh does not discard chat drafts or scroll position. Rich mentions, media, voice and resource links were added in v0.8.0.
- Fixed a duplicate SMTP queue send.
- Updated the in-app and external documentation and preserved the existing RTL Persian design, 120% desktop scale, LAN port 1939 and Jelofen creator signature.

## v0.6.1 · Secure joining and Persian calendar

- Added secure, shareable workspace join links for new and existing accounts.
- Existing registered users can accept email invitations by signing in; the invitation flow no longer rejects an already-registered email.
- Join tokens contain 48 bytes of cryptographically secure randomness; only SHA-256 hashes are stored. New links place the secret in the URL fragment and submit it in a POST body, avoiding token exposure in the initial request and URL path logs. Links support expiry, usage limits and revocation. HTTPS is still required to encrypt network traffic.
- Task deadlines and recurring-task start dates can be entered using the Jalali calendar. The calendar view, date labels and timestamps explicitly use the Persian calendar. Database dates remain ISO Gregorian for reliable sorting and API compatibility.
- Redesigned the creator signature as a black, professional popup with white contact links, violet Jelofen accent, five-second GitHub redirect and a stay/cancel option.
- Bumped app and static asset version to 0.6.1.

## v0.6.0 · MVP admin and reliability

- Multi-workspace account membership and switching.
- Configurable role and shared-folder permissions.
- TOTP two-factor authentication, recovery codes and password reset.
- Authenticated WebSocket events.
- Automatic and manual backups.

