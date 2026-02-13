from django.contrib import admin
from .models import Account, AccountMembership

# Register your models here.
admin.site.register(Account)
admin.site.register(AccountMembership)