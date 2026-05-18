from django.contrib import admin
from .models import Account, AccountMembership, AccountInvitation

# Register your models here.
admin.site.register(Account)
admin.site.register(AccountMembership)
admin.site.register(AccountInvitation)