# Feature: Source Edit + Delete

**Source:** `devdocs/appdocs/post_mvp.md` — sources section (edit); delete is an explicit scope addition not in the source docs
**Status:** Complete (tests pending)
**Target phase:** Post-MVP Phase 1

---

## Overview

The MVP allows users to create sources but provides no way to update or delete them. This feature adds an edit view (rename, update credentials) and a delete action. Credentials must remain encrypted on save. Edit and Delete controls are added to `source_detail.html`.

---

## Dependencies

- [x] `apps/sources/` — `Source` model, `SourceForm`, `encrypt_credentials`/`decrypt_credentials` utilities, and the existing create view (which this closely mirrors) must all be in place

---

## Implementation Checklist

### Phase 1 — Edit View

#### Views & URLs
- [x] `SourceUpdateView` — `GET /sources/<id>/edit/` — renders a pre-populated `SourceForm` with the source's current name, source type, and decrypted credential fields
- [x] `SourceUpdateView` — `POST /sources/<id>/edit/` — validates the form, re-encrypts credentials with Fernet, saves the updated `Source`, and redirects to `sources:detail`
- [x] Add `TenantQuerysetMixin` and `LoginRequiredMixin` to `SourceUpdateView` so users cannot edit sources belonging to other accounts
- [x] Register route `path('<int:pk>/edit/', views.SourceUpdateView.as_view(), name='edit')` in `apps/sources/urls.py`
- [x] `SourceDeleteView` — `POST /sources/<id>/delete/` — deletes the `Source` and redirects to `sources:list`; use Django's `DeleteView` with `LoginRequiredMixin` and `TenantQuerysetMixin`
- [x] Register route `path('<int:pk>/delete/', views.SourceDeleteView.as_view(), name='delete')` in `apps/sources/urls.py`

#### Forms
- [x] `SourceForm` pre-population — `SourceUpdateView.get_initial()` decrypts the stored credentials and populates `host`, `port`, `dbname`, `user`, and `password` fields so the form is not blank on load

#### Templates
- [x] `sources/source_form.html` — reuse for the edit view (it already exists); confirm the template works for both create and edit without changes, or make minimal adjustments (e.g., a dynamic 
  heading like "Edit Source" vs "Add Source")
- [x] `sources/source_detail.html` — add an "Edit" link pointing to `{% url 'sources:edit' source.pk %}` and a "Delete" button (POST form) pointing to `{% url 'sources:delete' source.pk %}`
- [x] `sources/source_delete.html` — confirmation page shown on `GET /sources/<id>/delete/` before the user confirms deletion

---

## Key Design Decisions

- **Re-use `SourceForm`:** The existing form already has all credential fields and styled widgets. The edit view should reuse it rather than creating a separate `SourceEditForm`.
- **Always re-encrypt on save:** The simplest safe approach is to always re-encrypt the credential dict from `form.cleaned_data` on every save, even if unchanged. This avoids needing to diff old vs. new values.
- **`UpdateView` base class:** Use Django's `UpdateView` (like `SourceCreateView` uses `CreateView`) to get `get_object()`, form binding, and `form_valid()` scaffolding for free.
- **Tenant scoping:** `TenantQuerysetMixin` restricts `get_queryset()` to the current account, so `get_object()` will 404 if someone tries to edit another account's source.

---

## Notes

- The `password` field uses `PasswordInput` widget, which intentionally does not echo the stored value back to the form. In `get_initial()`, populate it from the decrypted credentials so the user doesn't have to re-enter it if they only want to rename the source. Be aware this means the password is sent in plaintext in the HTML — acceptable for a dev/internal tool but worth noting.
- `SourceCreateView.form_valid()` manually handles encryption before calling `super()`. `SourceEditView.form_valid()` will need the same pattern: call `form.save(commit=False)`, build the credentials dict, encrypt, then save.