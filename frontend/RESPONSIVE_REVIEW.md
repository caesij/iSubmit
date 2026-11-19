# Responsive implementation review

## Scope and starting state

The task covers the existing Django HTML/CSS/JavaScript frontend: authentication, faculty, and admin/staff. The Git working tree was clean before this task. Earlier profile, notification, settings, and NLP placeholder changes were preserved. No commits, pushes, database writes, dependency installations, or backend changes were made.

## Audit and implementation sequence

Before editing application files, inspected the frontend tree, both portal bases, authentication base, inherited pages and includes, the three main stylesheets, frontend scripts, and the routes/forms/views used to render them. Captured read-only GET output and baseline screenshots. Implemented incrementally: authentication, faculty, admin/staff, shared component verification, then regression testing.

Existing organization remains intact:

- `accounts/auth_base.html` supplies login and password-reset layouts; `accounts/lockout.html` is standalone.
- Each portal has its own base and stylesheet. `data-portal` scopes the shell; `data-css` selects page modules.
- Existing page scripts manage polling, search, notifications, uploads, selection, forms, and dialogs. Their URLs, data attributes, IDs, CSRF tokens, request methods, and field names remain intact.
- Portal styles are not imported by authentication pages. The shared navigation script is loaded only by the two portal bases.
- Existing SVG/CSS charts and their data sources were retained.

Issues found:

- Mobile login panels combined `width: 100%` with content-box padding, causing horizontal overflow; the branding panel also retained desktop viewport height and large spacing.
- Portals changed their sidebar into a full navigation section above the content on phones, with no collapsible navigation.
- Fixed sidebar/search widths squeezed the faculty header at tablet widths.
- User-management filters overflowed at laptop and some desktop widths.
- My Submissions kept four cards across on phones.
- Notification card actions squeezed long messages into narrow columns; channel settings retained minimum-width grid tracks.
- Wide tables, form controls, profile details, preview panels, and dashboard headers needed local size/overflow handling.
- The account-lockout page lacked a viewport meta tag.
- Older presentation selectors carry ID-level specificity, so the bell positioning override must match that existing specificity.

## Files changed

| File | Purpose |
| --- | --- |
| `static/css/auth/login.css` | Correct mobile panel sizing and spacing, input sizes, password toggle targets, validation wrapping, and submit-button sizing. Desktop split-screen styles remain unchanged. |
| `static/css/auth/lockout.css` | Mobile-only long-account-name wrapping and a larger return-link target; preserve the unstyled desktop presentation. |
| `static/css/layout/faculty_portal.css` | Scoped shell, header, cards, filters, notifications, channel switches, profile, previews, upload confirmation, and touch-target adjustments. |
| `static/css/layout/admin_staff_portal.css` | Equivalent shell/component handling plus user filters, dashboard headers, submission filters, editors, and dialogs. |
| `static/js/portal-responsive.js` | Reuse the existing sidebar as an accessible drawer; add and remove local table scroll regions according to viewport size. |
| `templates/faculty_portal/base.html` | Load the shared script and add the sidebar identifier, menu toggle, close button, and overlay. |
| `templates/admin_staff_portal/base.html` | Same navigation hooks, preserving existing role-dependent links and subnavigation. |
| `templates/accounts/lockout.html` | Add one viewport tag and the scoped lockout stylesheet. |
| `RESPONSIVE_REVIEW.md` | Audit, changes, validation evidence, limitations, and manual handoff. |

Paths in this table are relative to `frontend/`.

## Resulting behavior

### Login and authentication

At 900px and below, branding and forms stack with border-box sizing, reduced branding height/spacing, flexible role buttons, readable inputs, and reachable submit controls. At 480px and below, padding and branding text scale further. Password reset and error states inherit the same sizing. No authentication logic changed. Browser zoom remains enabled.

### Faculty portal

At tablet/phone widths, the main area uses the available width. Header controls wrap, search gets its own row on phones, and the user badge remains available. Dashboard sections, submission statistics, document filters, profiles, and preview panels adapt to narrower layouts. Notification actions stack separately from the full message. Both notification delivery channels remain available. Upload controls retain their original forms and handlers; removal confirmations fit short viewports.

### Admin/staff portal

The same responsive shell covers management, programs/courses, documents, submissions, notifications, profiles, and settings. Forms and filter rows wrap or stack. Tables retain their columns and actions through local scrolling. Preview panels stack; requirement and program confirmation dialogs stay within the viewport. Dashboard tabs and View All wrap on small phones. User filters wrap where their original row would overflow.

### Shared navigation and tables

- Existing navigation links and active indicators are reused, with no duplicate navigation list.
- The drawer supports the close button, overlay, Escape, Tab/Shift+Tab focus containment, restored opener focus, `aria-expanded`, and `aria-controls`.
- Background content is inert and body scrolling is locked only while the drawer is open.
- Closing or switching to desktop clears the mobile state. The desktop sidebar retains its original layout.
- Without JavaScript, navigation remains visible in normal flow on small screens.
- Wide tables get a labelled, focusable horizontal scroll region on small screens. Wrappers are removed on desktop, preserving the original desktop table DOM.
- No global `overflow-x: hidden`, hidden essential columns, new frameworks, or duplicated viewport tags were introduced.

## Breakpoints

| Width | Purpose |
| --- | --- |
| 1600px and below | Admin/staff user-management filter wrapping only. |
| 1024px and below | Portal drawer, fluid header/content, table scroll regions, narrower grid/preview layouts. |
| 900px and below | Stacked authentication layout; mobile lockout text handling. |
| 600px and below | Phone form/card/filter layouts, notification stacking, channel grids, touch targets, bounded dialogs. |
| 480px and below | Compact login branding and padding. |

Existing page-specific media queries remain in place. Responsive additions are grouped in their original portal stylesheet and scoped to that portal.

## Automated and visual verification

Tests use the installed headless Microsoft Edge/Playwright tooling and the site's existing Poppins font weights cached under `.cache/responsive/`. No test requests reach production. Django renders use read-only transactions; unavailable document states use explicitly labelled, isolated template fixtures.

- Layout matrix: 52 page/state renders at 320, 360, 375, 390, 414, 480, 768, 1024, 1280, 1366, 1440, and 1920px. Final result: **624 checks passed with zero page-level horizontal overflow and zero missing local static assets**.
- Coverage includes authentication/reset/error/lockout states; dashboards; user lists/forms; programs/courses; submission bins/editor/detail; faculty submissions; notification lists; profiles; settings; search; and empty/populated document lists and preview fixtures.
- Actual current Django-rendered HTML is used where the view can safely render. Fixtures cover missing data, failing views, and views that attempt writes or acquire update locks on GET.
- Interaction checks passed for drawer open/close/overlay, focus trap and return, inert state, scroll lock, viewport switching, profile edit/cancel, unread count, notification/search dropdown fit, table keyboard scrolling, enabled file picker, upload-removal confirmation cancellation, requirement dialog fit at 320x568, NLP placeholder preservation, user action menus after table scrolling, program deletion cancellation, login role switching, and password visibility.
- Tablet and 812x375 landscape navigation checks passed. No actual login, final upload, save, approval, notification mutation, or deletion was submitted.
- The interaction run recorded no uncaught page errors, missing local static assets, or mutating requests. Background API polling and WebSockets are isolated in the browser harness; this does not validate their live transport.
- `python manage.py check` in the running Docker web container passed. `git diff --check` passed.
- All standalone web page templates have one viewport meta tag; the existing email template was left unchanged.

### Desktop preservation

Compared visible element geometry across 52 page/state renders at 1280, 1440, and 1920px: 156 comparisons. All were identical except the faculty/staff user-management filter pages at 1280 and 1440px, where wrapping intentionally fixes existing overflow. All 52 comparisons at 1920px were identical.

Also compared 14 before/after PNG pairs for login, both dashboards, both profiles, the period editor, and user management at 1440/1920px. Thirteen PNG pairs were byte-identical. The sole difference was the intended user-management filter wrapping at 1440px.

## Existing blockers and verification limits

These are not caused by the responsiveness changes and were not modified:

| Area | Observed limitation | Frontend verification used |
| --- | --- | --- |
| Admin document repository/archive | `backend/admin_staff_portal/helpers/document_repo.py` refers to `Requirement.Semester` and requirement-level term fields that are no longer on that model. | Empty and populated template fixtures. |
| Faculty My Documents/Pinned | `backend/faculty_portal/helpers/my_documents.py` uses old requirement-level academic-year lookups, producing `FieldError`. | Empty/populated document templates and preview fixtures. |
| Staff Permissions | The development database lacks `accounts_staffpermission`. | Isolated template fixture; no schema or migration changes. |
| Staff dashboard | No active STAFF account exists in this environment. | Staff dashboard template fixture, rather than an authenticated STAFF workflow. |
| Account security | `backend/accounts/security.py:get_login_activity` deletes stale records on GET, so the view cannot execute in the read-only test transaction. | Render the actual template with `PasswordChangeForm` and an empty login-activity collection. |
| Edit requirement GET | Uses `SELECT FOR UPDATE`, disallowed by the read-only capture. | Render its actual form/fragment with existing requirement settings and test dialog opening via an isolated response. |
| Document previews/review | The selected faculty account has no suitable submitted-document records for all preview states. | Synthetic template data; real PDF rendering/downloads and populated review histories remain manual checks. |

No backend change is needed for these responsive styles. Restoring the failing live document lists would require separately approved backend work to align the two helpers with the current period relationships; no frontend-only change can repair those ORM queries. The missing staff-permission table requires a separate schema/migration investigation and approval. No such work was performed or is assumed authorized.

Physical iOS/Android browsers, the software keyboard, device file pickers, actual PDF rendering, screen-reader announcements, live WebSocket/polling updates, valid/invalid server submissions, and backend search/filter/pagination results were not fully exercised by the isolated browser tests. CSS adapts their interfaces, but end-to-end success is not claimed.

## Recommended manual checks

1. On iOS Safari and Android Chrome, sign in with faculty, staff, and admin test accounts; try portrait/landscape and the software keyboard.
2. Open/close navigation using touch and a keyboard; rotate with the drawer open, then resize to desktop.
3. In the approved development environment, upload/replace a test document, select it, submit it, and verify existing server validation and status updates.
4. With representative data, scroll all management tables and use search, filters, pagination, action menus, and document download/preview controls.
5. Exercise requirement validation, user teaching assignments, settings switches, and short-screen dialogs without changing production records.
6. Check notifications arriving and becoming read through the real backend, and confirm dashboard charts update at each layout size.
7. Run a screen-reader pass and browser zoom checks; check device safe areas and native PDF/file-picker behavior.

## Local evidence and reruns

Ignored QA files are under `.cache/responsive/`: `render.py`, `fixtures.py`, `layout.py`, `interactions.py`, and `desktop.py`. They depend on the existing local `.cache/frontend-tools` Playwright installation and Edge path; they are development helpers, not a new project dependency or portable CI suite.

- `baseline/capture-results.json` and `current/capture-results.json`: live-render status and existing blockers.
- `final/layout-all.json`: final viewport results and missing-asset list.
- `interaction-results.json`: interaction assertions and error/mutation records.
- `desktop-results.json` and `pixel-results.json`: desktop geometry and PNG comparisons.
- `baseline/screenshots/`, `desktop/before/`, `desktop/after/`, `mobile-review/screenshots/`, and `interactions/`: screenshot evidence.

These cache files can contain development account details and should remain uncommitted. No preview server was started; headless browsers exit when their checks finish.
