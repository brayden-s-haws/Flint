""" These forms are used for various aspects of account management and invitation handling. """
from __future__ import annotations

from django.forms import ModelForm
from django.core.exceptions import ValidationError

from .models import Account, AccountInvitation, AccountMembership


class AccountSettingsForm(ModelForm):
    class Meta:
        model = Account
        fields = ['name']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'w-full bg-flint-card border border-flint-border-em rounded-md px-3 py-2 text-sm text-flint-text focus:outline-none focus:ring-2 focus:ring-flint-orange'})


class AccountInviteForm(ModelForm):
    class Meta:
        model = AccountInvitation
        fields = ['email', 'role']

    def clean_email(self):
        """
        Clean email used for two important checks, does the email already belong to an existing account member or an existing invitation.
        :return:
        """
        email = self.cleaned_data['email']
        if AccountMembership.objects.filter(account=self.account, user__email=email).exists():
            raise ValidationError('This email is already in use.')
        if AccountInvitation.objects.filter(account=self.account, email=email, accepted=False).exists():
            raise ValidationError('An invitation has already been sent to this email.')
        return email

    def __init__(self, *args, **kwargs):
        self.account = kwargs.pop('account') # Callers must pass the account instance or raise an error. clean_email relies on self.account to be able to run its checks.
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'w-full bg-flint-card border border-flint-border-em rounded-md px-3 py-2 text-sm text-flint-text focus:outline-none focus:ring-2 focus:ring-flint-orange'})