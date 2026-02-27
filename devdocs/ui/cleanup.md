# UI Cleanup Tracker

Items to revisit when polishing the UI. Not blockers — functional code comes first.

---

## Messages

- [x] **Style Django messages with Tailwind** — `templates/base.html` lines 28-33. Currently using generic `class="messages"` on the `<ul>` and Django's message tags (`success`, `error`, `warning`,
  `info`) on `<li>` elements. These tags don't map to any Tailwind classes. Need to either map tags to Tailwind utility classes (e.g., green background for success, red for error) or extract messages into a `components/_messages.html` partial.

---

## Navigation

- [ ] **Wire up nav links** — `templates/base.html` lines 18-24. Placeholder links with empty `href=""`. Replace with real `{% url %}` tags as views are built. (this is actually in components/_navbar.html )
- [ ] **Add auth-aware nav** — Show login/register when logged out, show user info/logout when logged in.
- [ ] **Swap Login/Register button hierarchy** — `templates/components/_navbar.html`. Currently Login has the prominent blue button style and Register has the plain text link. Convention is the opposite — Register (the sign-up CTA) should be the filled button, Login the plain link.

---

## Forms

- [ ] **Style all form inputs** — All forms across the project render Django's default unstyled widgets. At MVP completion, do a pass over every form class (`RegistrationForm`, `LoginForm`, `SourceForm`, and any others added) and add an `__init__` method that calls `field.widget.attrs.update({'class': '...'})` on each field. Also update label rendering in templates. Target input classes: `w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500`. Target label classes: `block text-sm font-medium text-gray-700 mb-1`.

---

## Dashboard

- [ ] **Wire up stat card "View all" links** — `templates/core/dashboard.html` lines 20, 25, 30. Currently `href=""` placeholders. Replace with `{% url 'sources:list' %}`, `{% url 'catalog:list' %}`, and `{% url 'insights:list' %}` once each app has its list view defined.
- [ ] **Wire up empty state CTA button** — `templates/core/dashboard.html` line 39. Currently `href=""`. Replace with `{% url 'sources:list' %}` once the sources list view exists.
- [ ] **Flesh out dashboard active state** — `templates/core/dashboard.html`. The `{% if source_count > 0 %}` block is currently a placeholder. Return to this after the sources and catalog apps are complete. At that point: update `DashboardView.get_context_data` in `apps/core/views.py` to query real counts (`Source`, `Table`, `Insight` models), and build out the active state section with a recent sources list, recently discovered tables, and latest insights.

---

## General

- [ ] **Tailwind CDN to production build** — Currently using the CDN play script. Swap to a proper Tailwind build step before production.
