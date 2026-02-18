# UI Cleanup Tracker

Items to revisit when polishing the UI. Not blockers — functional code comes first.

---

## Messages

- [ ] **Style Django messages with Tailwind** — `templates/base.html` lines 28-33. Currently using generic `class="messages"` on the `<ul>` and Django's message tags (`success`, `error`, `warning`, `info`) on `<li>` elements. These tags don't map to any Tailwind classes. Need to either map tags to Tailwind utility classes (e.g., green background for success, red for error) or extract messages into a `components/_messages.html` partial.

---

## Navigation

- [ ] **Wire up nav links** — `templates/base.html` lines 18-24. Placeholder links with empty `href=""`. Replace with real `{% url %}` tags as views are built.
- [ ] **Add auth-aware nav** — Show login/register when logged out, show user info/logout when logged in.

---

## General

- [ ] **Tailwind CDN to production build** — Currently using the CDN play script. Swap to a proper Tailwind build step before production.
