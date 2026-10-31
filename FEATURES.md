# Stash — feature list

Priority:

- **P0** — MVP. Ships in v1.
- **P1** — Soon after launch.
- **P2** — Later. Only if users ask for it.

The milestone column points to `PLAN.md` §11.

---

## 1. Accounts and sign-in

| # | Feature | Priority | Milestone |
| --- | --- | --- | --- |
| 1.1 | Sign up with email and password | P0 | M1 |
| 1.2 | Verify email by a link sent over SMTP (SES) | P0 | M1 |
| 1.3 | Resend the verification email | P0 | M1 |
| 1.4 | Log in with email and password | P0 | M1 |
| 1.5 | Forgot password: emailed reset link, single use, expires in 30 min | P0 | M1 |
| 1.6 | Sign in with Google | P0 | M2 |
| 1.7 | Sign in with X | P0 | M2 |
| 1.8 | JWT session in HttpOnly cookies, silent refresh, stays signed in for 30 days | P0 | M1 |
| 1.9 | Log out (this device) | P0 | M1 |
| 1.10 | Password strength meter on sign-up and reset | P1 | M10 |
| 1.11 | Link or unlink Google and X from settings | P1 | M2 |
| 1.12 | Set a password on an OAuth-only account | P1 | M10 |
| 1.13 | Log out of all devices | P1 | M10 |
| 1.14 | Edit profile: display name, avatar | P1 | M10 |
| 1.15 | Delete account and all data | P1 | M10 |
| 1.16 | Change email (verify the new address) | P2 | — |
| 1.17 | Two-factor authentication (TOTP) | P2 | — |

## 2. Dashboard

| # | Feature | Priority | Milestone |
| --- | --- | --- | --- |
| 2.1 | Grid of the user's canvases: title, last edited time, item count | P0 | M3 |
| 2.2 | Create a new canvas | P0 | M3 |
| 2.3 | Rename a canvas (inline) | P0 | M3 |
| 2.4 | Delete a canvas (soft delete, with confirm) | P0 | M3 |
| 2.5 | Sort by last edited / name | P0 | M3 |
| 2.6 | Empty state with a "Create your first canvas" action | P0 | M3 |
| 2.7 | Search canvases by title | P1 | M10 |
| 2.8 | Duplicate a canvas | P1 | M10 |
| 2.9 | Canvas thumbnail preview | P1 | M10 |
| 2.10 | Trash: restore deleted canvases within 30 days | P1 | M10 |
| 2.11 | Pin / favourite canvases | P2 | — |
| 2.12 | Folders or tags for canvases | P2 | — |

## 3. Canvas

### 3.1 The space

| # | Feature | Priority | Milestone |
| --- | --- | --- | --- |
| 3.1.1 | Infinite canvas: pan (drag, space+drag, trackpad) and zoom (wheel, pinch) | P0 | M4 |
| 3.1.2 | Excalidraw-style look: dot grid, minimal floating toolbar, hand-drawn font option | P0 | M4 |
| 3.1.3 | Light and dark mode | P0 | M4 |
| 3.1.4 | Zoom controls: in, out, reset, fit to content | P0 | M4 |
| 3.1.5 | Minimap | P1 | M4 |
| 3.1.6 | Snap to grid toggle | P1 | M10 |
| 3.1.7 | Remembers where you were (viewport) per canvas | P0 | M4 |

### 3.2 Content you can add

| # | Feature | Priority | Milestone |
| --- | --- | --- | --- |
| 3.2.1 | **Link card**: favicon, title, site name, description, preview image, URL; opens in a new tab | P0 | M5 |
| 3.2.2 | Link card loading and "couldn't fetch preview" states, with a retry | P0 | M5 |
| 3.2.3 | **Note**: sticky note with markdown (headings, bold, italics, lists, checkboxes, links) | P0 | M4 |
| 3.2.4 | Note colours | P0 | M4 |
| 3.2.5 | **Text**: free text label on the canvas, font size | P0 | M4 |
| 3.2.6 | **Code block**: syntax highlighting, language picker, copy button | P0 | M4 |
| 3.2.7 | Add a personal comment on a link card (searchable) | P1 | M5 |
| 3.2.8 | Rich embeds for YouTube, X posts and GitHub repos | P1 | — |
| 3.2.9 | Arrows / connectors between cards | P1 | — |
| 3.2.10 | Group / frame: a named box that holds cards | P2 | — |
| 3.2.11 | **Image card**: upload JPEG, PNG, WebP or GIF (≤ 10 MB) to private S3; thumbnail, caption, click for full size; shown only after the safety check passes | P0 | M5b |
| 3.2.11a | Other file uploads (PDF, docs) | P2 | — |
| 3.2.12 | Freehand drawing and shapes | P2 | — (see PLAN §14.3) |

### 3.3 Adding content quickly

| # | Feature | Priority | Milestone |
| --- | --- | --- | --- |
| 3.3.1 | Toolbar buttons for each card type | P0 | M4 |
| 3.3.2 | Double-click empty space → new note | P0 | M4 |
| 3.3.3 | Paste: a URL becomes a link card, fenced code becomes a code card, other text becomes a note | P0 | M4/M5 |
| 3.3.4 | Drag a URL from another tab onto the canvas | P1 | M5 |
| 3.3.4a | Paste a screenshot or drag image files onto the canvas → image cards | P0 | M5b |
| 3.3.4b | Storage used / quota shown in settings (500 MB in v1) | P0 | M5b |
| 3.3.5 | Paste several URLs at once → several link cards laid out in a grid | P1 | M10 |
| 3.3.6 | Browser extension / bookmarklet: "save to Stash canvas" | P2 | — |

### 3.4 Editing

| # | Feature | Priority | Milestone |
| --- | --- | --- | --- |
| 3.4.1 | Select, multi-select (shift-click, drag box), move, resize | P0 | M4 |
| 3.4.2 | Delete selected | P0 | M4 |
| 3.4.3 | Undo / redo | P0 | M4 |
| 3.4.4 | Copy, paste and duplicate cards | P0 | M4 |
| 3.4.5 | Bring to front / send to back | P1 | M4 |
| 3.4.6 | Align and distribute selected cards | P2 | — |
| 3.4.7 | Keyboard shortcuts: `N` note, `T` text, `L` link, `C` code, `Delete`, `Ctrl+Z`, `Ctrl+Shift+Z`, `Ctrl+D`, `?` for the shortcut sheet | P0 | M4 |
| 3.4.8 | Shortcut cheat sheet (`?`) | P1 | M10 |

### 3.5 Saving

| # | Feature | Priority | Milestone |
| --- | --- | --- | --- |
| 3.5.1 | Autosave, no save button; a "Saved / Saving… / Offline" indicator | P0 | M4 |
| 3.5.2 | Same canvas open in two tabs: no silent overwrite (conflict detection) | P0 | M4 |
| 3.5.3 | Warn before closing the tab with unsaved changes | P0 | M4 |
| 3.5.4 | Export a canvas as JSON or Markdown | P1 | M10 |
| 3.5.5 | Import a JSON export | P2 | — |
| 3.5.6 | Version history for a canvas | P2 | — |

## 4. Chat: find and highlight

| # | Feature | Priority | Milestone |
| --- | --- | --- | --- |
| 4.1 | Floating chat button; drawer slides in from the right; canvas stays usable | P0 | M7 |
| 4.2 | Ask in plain language ("the Stripe pricing link", "my notes about onboarding") | P0 | M7 |
| 4.3 | Matching cards get a pulsing outline; the rest dim; the view pans and zooms to fit them | P0 | M7 |
| 4.4 | Search finds both meaning and exact words (names, URLs, codes, dates) | P0 | M7 |
| 4.5 | Scope toggle: this canvas / all canvases | P0 | M7 |
| 4.6 | Results on another canvas: a chip that opens that canvas and highlights the card | P0 | M7 |
| 4.7 | Streamed AI answer that cites cards as `[1]`, `[2]`; clicking a citation focuses that card | P0 | M8 |
| 4.8 | Honest "Nothing on your canvas matches that." when nothing fits — no made-up answers | P0 | M8 |
| 4.9 | Follow-up questions use the last few messages | P0 | M8 |
| 4.10 | Clear highlight: close the drawer, press `Esc`, or click empty canvas | P0 | M7 |
| 4.11 | Chat history per canvas, with a "clear history" button | P1 | M8 |
| 4.12 | Step through results (next / previous card) | P1 | M10 |
| 4.13 | Suggested questions when the drawer opens | P1 | M10 |
| 4.14 | Summarise a selection of cards | P2 | — |
| 4.15 | "Tidy up": AI suggests grouping related cards (user approves before anything moves) | P2 | — |
| 4.16 | Voice input | P2 | — |

## 4a. Reminders and email digests

| # | Feature | Priority | Milestone |
| --- | --- | --- | --- |
| 4a.1 | "Remind me" on any card: later today, tomorrow 9:00, next Monday, or a custom time | P0 | M8a |
| 4a.2 | Reminder email with the card and a button that opens the canvas with that card highlighted | P0 | M8a |
| 4a.3 | Bell chip on cards with a pending reminder; reschedule or cancel from the chip | P0 | M8a |
| 4a.4 | Reminders panel: upcoming and past | P0 | M8a |
| 4a.5 | Free-standing reminder with just a note | P1 | M8a |
| 4a.6 | **Daily digest** email at 08:00 local: yesterday's points noted, grouped by canvas, plus today's reminders | P0 | M8a |
| 4a.7 | **Weekly digest** email on Monday: the week's points noted and next week's reminders | P0 | M8a |
| 4a.8 | AI "key points" (3–5 bullets) in digests, from safe cards only, with a plain-list fallback | P0 | M8a |
| 4a.9 | No empty digests; never sent twice for the same period | P0 | M8a |
| 4a.10 | Settings: daily on/off, weekly on/off, send hour, time zone; one-click unsubscribe in every digest | P0 | M8a |
| 4a.11 | "Remind me" from chat ("remind me about the Stripe link on Friday") | P1 | — |

## 5. Safety, limits and privacy

These are not visible features, but users rely on them.

| # | Feature | Priority | Milestone |
| --- | --- | --- | --- |
| 5.1 | Each user sees only their own canvases, cards and chat — enforced in every query | P0 | M3 |
| 5.2 | Rate limits on login, sign-up, password reset and chat; friendly "try again in N seconds" message | P0 | M1/M8 |
| 5.3 | No account enumeration on forgot-password | P0 | M1 |
| 5.4 | Link previews cannot reach internal addresses (SSRF protection) | P0 | M5 |
| 5.5 | Text inside cards cannot steer the AI (treated as data) | P0 | M8 |
| 5.6 | Monthly AI budget per user, and a server-side switch to turn AI off | P0 | M8 |
| 5.7 | Secrets never in the browser; HTTPS everywhere | P0 | M9 |
| 5.8 | Privacy page: what is stored, where (Neon Singapore, AWS Mumbai), what is sent to the AI | P1 | M10 |

### 5a. Content guardrails: adult and abusive content is never sent

Details in `PLAN.md` §7a.

| # | Feature | Priority | Milestone |
| --- | --- | --- | --- |
| 5a.1 | Every chat question is checked (word list + Bedrock Guardrails) **before** it is embedded or sent to the model; adult, hateful, insulting or harassing questions get "I can't help with that." | P0 | M8 |
| 5a.2 | Every card's text is checked before embedding; flagged cards are never sent to Voyage or Mantle and never appear in chat results | P0 | M5a |
| 5a.3 | "Hidden from AI" badge on flagged cards, showing the category | P0 | M5a |
| 5a.4 | Adult-domain blocklist: such links are saved as a plain URL, no fetch, no preview image, no AI | P0 | M5a |
| 5a.5 | Flagged link metadata hides the preview image | P0 | M5a |
| 5a.6 | AI answers are checked sentence by sentence before the browser sees them; a bad sentence stops the answer | P0 | M8 |
| 5a.7 | Cards that try to instruct the AI ("ignore previous instructions…") are flagged as prompt attacks | P0 | M5a |
| 5a.8 | Fail closed: if the safety check is down, nothing goes to the AI ("Try again in a moment") | P0 | M5a |
| 5a.9 | Sexual content involving minors is refused at save and never stored | P0 | M5a |
| 5a.10 | Repeated abusive questions pause chat (15 min, then 24 h) | P0 | M8 |
| 5a.11 | Moderation log keeps categories and ids only, never the text | P0 | M5a |
| 5a.12 | Red-team test set (block rate and false-positive rate) run on every safety change | P0 | M5a |
| 5a.13 | "This was a mistake" button on a flagged card → operator review queue | P1 | M10 |
| 5a.14 | Every uploaded image passes the image content filter before it is shown; blocked images are deleted from storage. Location data (EXIF/GPS) is stripped | P0 | M5b |
| 5a.15 | Share links refuse canvases with flagged cards | P2 | with sharing |

## 6. Responsive and accessibility

| # | Feature | Priority | Milestone |
| --- | --- | --- | --- |
| 6.1 | Works on desktop Chrome, Safari, Firefox, Edge | P0 | M4 |
| 6.2 | Phone and tablet: view canvases, pan/zoom, use chat; editing limited | P1 | M10 |
| 6.3 | Keyboard navigation for auth pages, dashboard and chat drawer | P1 | M10 |
| 6.4 | Visible focus, labels for screen readers, highlight not shown by colour alone | P1 | M10 |
| 6.5 | Respects "reduce motion" (no pulse or animated pan) | P1 | M10 |

## 7. Onboarding

| # | Feature | Priority | Milestone |
| --- | --- | --- | --- |
| 7.1 | New users get a starter canvas showing each card type and a sample chat question | P1 | M10 |
| 7.2 | Short first-run hints: paste a link, double-click for a note, open chat | P1 | M10 |

## 8. Operator features (for you, not users)

| # | Feature | Priority | Milestone |
| --- | --- | --- | --- |
| 8.1 | `/health` and `/health/ready` | P0 | M0 |
| 8.2 | JSON logs with a request id on every line | P0 | M0 |
| 8.3 | AI trace per chat request: model, tokens, latency, cited cards, outcome | P0 | M8 |
| 8.4 | Golden-set eval command for chat quality | P0 | M7/M8 |
| 8.5 | Re-index command (re-embed all cards) | P0 | M6 |
| 8.6 | One-command deploy and push-to-deploy | P0 | M9 |
| 8.7 | Usage view: users, canvases, cards, AI spend per day | P2 | — |

## 9. Canvas additions, rated for production feasibility

Ideas to make the canvas better, judged on what they cost to build and to run on one `t4g.small` + Neon + paid APIs.

- **Effort:** S = days, M = 1–2 weeks, L = a month or more.
- **Run cost:** what it adds to the monthly bill or to server load.
- **Risk:** what can go wrong in production.

### Do these: high value, cheap to run

| Feature | What it is | Effort | Run cost | Risk | Priority |
| --- | --- | --- | --- | --- | --- |
| **Quick find (`Ctrl+K`)** | Instant keyword search across all canvases, no AI; jumps to and highlights the card | S | None (Postgres full-text index already exists) | None | **P0** |
| **Duplicate link warning** | "You saved this link on *Research* 3 days ago" when pasting a URL already saved | S | None (normalised-URL index) | None | **P0** |
| **Tags on cards** | `#tag` chips; filter the canvas by tag; tags feed search | S | None | None | P1 |
| **Related cards** | Side panel showing the 5 most similar cards from any canvas | S | **None** — reuses the stored embeddings, no new API calls | Must apply the same owner + `safety_state` filter | P1 |
| **Arrows between cards** | Connect cards with a labelled arrow | S | None (React Flow edges) | None | P1 |
| **Frames / sections** | A named box; moving it moves its cards; collapse it | M | None (React Flow parent nodes) | Nested drag edge cases | P1 |
| **Checklist card** | To-do list with progress; optional due date | S | None | None | P1 |
| **Table card** | Small editable markdown table | S | None | None | P1 |
| **Canvas templates** | Start from "Reading list", "Research board", "Project ideas", "Trip planning" | S | None (seed JSON) | None | P1 |
| **List / outline view** | The same canvas as a sorted list; the natural phone layout and good for screen readers | M | None | None | P1 |
| **Dead-link check** | Weekly worker job marks links that now return 404 | S | Tiny (one HEAD request per link per week) | Rate-limit per domain; reuse the SSRF-safe fetcher | P1 |
| **Rich embeds** | Inline YouTube, Spotify, Figma, GitHub, X via oEmbed | M | None | Allowlist the providers; sandboxed iframes; strict CSP | P1 |

### Worth it, with limits

| Feature | What it is | Effort | Run cost | Risk | Priority |
| --- | --- | --- | --- | --- | --- |
| **AI link summary** | 2–3 line summary on a link card, generated once when it is saved | M | Mantle tokens per new link (~$ small); counts against the user's AI budget | Page text is untrusted: guardrail check on both page text and summary; summary only, no actions | P1 |
| **Auto-tag suggestions** | Suggest 1–3 tags for a new card; user accepts with one click | S | Small (one short Mantle call, or free nearest-neighbour from existing tags) | Never applied without a click | P1 |
| **Web clipper extension** | Save the current page or a selected quote to a chosen canvas | M | None on the server | Chrome Web Store review; reuses the same API and guardrails | P2 |
| **Email-to-canvas** | Forward an email or link to `save@…` and it lands on an "Inbox" canvas | M | SES inbound (cents) | Spam: accept only from the user's verified address; guardrail-check the body | P2 |
| **Read-only share link** | Public link to view one canvas | M | CDN-cacheable reads | **Public content needs moderation**: refuse if any card is flagged (5a.14), report button, unguessable links, revocable | P2 |
| **Version history** | Restore a canvas to an earlier save | M | Storage grows; keep 30 days | Prune job required | P2 |
| **Image cards** | Upload images to a private S3 bucket | M | S3 storage + transfer (low) | Image moderation required before display (Guardrails image filter), size and type caps, presigned URLs, no EC2 disk | **P0 — moved to v1 (M5b)** |

### Not now: cost or risk too high for one small server

| Feature | Why it waits |
| --- | --- |
| Real-time multi-user editing | Needs WebSockets, a CRDT (Yjs), presence, and a sticky or shared session layer; changes the save model. A v2 project |
| Freehand drawing and shapes | Changes the canvas library decision (tldraw licence or Excalidraw); weak fit for retrieval because strokes have no text |
| PDF and document cards | Parsing is heavy (Docling needs far more than 2 GB RAM) or paid per page (LlamaParse); add with a separate worker instance |
| Offline editing | Local-first sync and conflict merging; large effort for a web-first product |
| Native mobile apps | The responsive web app and list view cover phones first |

**Recommended next additions:** Quick find and duplicate-link warning in v1 (both free), then tags, related cards, arrows, frames, templates and list view as the first post-launch release. Together they make the canvas noticeably better and add nothing to the monthly bill.

## Later: possibly v2

- Share a canvas read-only by link.
- Invite collaborators with real-time co-editing.
- Public templates.
- Mobile app.
- Import from Pocket, Raindrop or browser bookmarks.
- Teams and paid plans.

---

**Counts:** 88 P0 (the v1 scope, milestones M0–M9), 45 P1, 20 P2. Arrows, rich embeds and image cards appear in both §3.2 and §9.
