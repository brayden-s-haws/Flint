from __future__ import annotations

# TODO(stub): Import forms from django — you need ModelForm, CharField, IntegerField,
#             and PasswordInput. All from django.forms.

# TODO(stub): Import Source from .models.


class SourceForm:
    # TODO(stub): This is a ModelForm — inherit from forms.ModelForm.
    #             It binds to Source but the credential fields (host, port, dbname,
    #             user, password) are NOT on the Source model. They are extra fields
    #             declared directly on this class and handled manually in form_valid.

    # TODO(stub): Declare the five credential fields explicitly on the class
    #             (before the Meta class). These are non-model fields — Django will
    #             include them in cleaned_data but NOT try to write them to the DB.
    #
    #               host     — forms.CharField(max_length=255)
    #               port     — forms.IntegerField(initial=5432)
    #                          IntegerField validates that the value is a whole number;
    #                          initial=5432 pre-fills the field with the PostgreSQL default.
    #               dbname   — forms.CharField(max_length=255)
    #               user     — forms.CharField(max_length=255)
    #               password — forms.CharField(widget=forms.PasswordInput)
    #                          PasswordInput renders an <input type="password"> so the
    #                          value is masked in the browser and not echoed back on error.

    class Meta:
        # TODO(stub): Set model = Source.

        # TODO(stub): Set fields = ['name', 'source_type'].
        #             These are the only two Source model fields the user fills in directly.
        #             DO NOT include 'credentials' — it is built from the five credential
        #             fields above and encrypted before saving (done in form_valid, not here).
        #             DO NOT include 'account' or 'first_synced_at' — both are set
        #             programmatically in form_valid, never from user input.
        ...