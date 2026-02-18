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

## Forms

- [ ] **Style registration form inputs** — `templates/users/register.html`. Plain browser-default inputs render correctly but are unstyled. Add `__init__` to `RegistrationForm` in `apps/users/forms.py` and call `field.widget.attrs.update({'class': '...'})` on each field. Also pass `attrs={"class": "..."}` to each `label_tag` call in the template. Target input classes: `w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500`. Target label classes: `block text-sm font-medium text-gray-700 mb-1`.

---

## General

- [ ] **Tailwind CDN to production build** — Currently using the CDN play script. Swap to a proper Tailwind build step before production.
