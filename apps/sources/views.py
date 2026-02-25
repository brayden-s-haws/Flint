from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView
from django.urls import reverse_lazy
from django.http import HttpResponse
from django.forms import BaseModelForm
from apps.core.mixins import TenantQuerysetMixin

from .models import Source
from .forms import SourceForm
from .encryption import encrypt_credentials


class SourceListView:
    # TODO(stub): Inherit from LoginRequiredMixin, TenantQuerysetMixin, ListView — in that order.
    #             MRO matters: LoginRequiredMixin must come first so auth redirect happens
    #             before TenantQuerysetMixin tries to access request.account.

    # TODO(stub): Set model = Source.

    # TODO(stub): Set template_name = 'sources/source_list.html'.
    #             The template does not exist yet — create it at that path under templates/.

    # TODO(stub): Set context_object_name = 'sources'.
    #             This is the name used in the template to iterate over the queryset
    #             (e.g., {% for source in sources %}).

    # TODO(stub): No extra methods needed — TenantQuerysetMixin handles queryset filtering
    #             and ListView handles pagination and context automatically.
    ...


class SourceCreateView:
    # TODO(stub): Inherit from LoginRequiredMixin, CreateView — in that order.
    #             TenantQuerysetMixin is NOT used here (it filters existing objects;
    #             we're creating a new one). Account assignment happens in form_valid instead.

    # TODO(stub): Set model = Source.

    # TODO(stub): Set form_class = SourceForm.
    #             SourceForm is a ModelForm that collects host, port, dbname, user, password.
    #             It must be created in apps/sources/forms.py before this view can work.

    # TODO(stub): Set template_name = 'sources/source_form.html'.

    # TODO(stub): Set success_url = reverse_lazy('sources:list').
    #             After a successful save, redirect the user to the source list.

    def form_valid(self, form):
        # TODO(stub): Type hint: form_valid(self, form: BaseModelForm) -> HttpResponse

        # TODO(stub): Step 1 — call form.save(commit=False) to get an unsaved Source instance.
        #             commit=False prevents a database write so you can mutate the object first.

        # TODO(stub): Step 2 — build the credentials dict from the raw form field values.
        #             The fields you need are host, port, dbname, user, password.
        #             Access them via form.cleaned_data['field_name'].
        #             Note: port is an integer in cleaned_data — json.dumps handles int fine,
        #             but consider whether you want to normalize it to str here.

        # TODO(stub): Step 3 — call encrypt_credentials(credentials_dict) and assign the
        #             result to source.credentials. This replaces the raw values with the
        #             Fernet-encrypted string before saving.

        # TODO(stub): Step 4 — assign source.account = self.request.account.
        #             request.account is attached by TenantMiddleware. This is how the new
        #             Source gets scoped to the correct tenant.

        # TODO(stub): Step 5 — call source.save() to write the record to the database.

        # TODO(stub): Step 6 — call super().form_valid(form) and return its result.
        #             This triggers the success_url redirect. Pass the already-saved instance
        #             by setting self.object = source before calling super(), so CreateView
        #             knows not to save again.
        ...
