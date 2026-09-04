""" Root URL configuration: mounts the Django admin and includes each app's URLconf under its path prefix. """
from django.contrib import admin
from django.urls import path, include


urlpatterns = [
    path('admin/', admin.site.urls),

    # App URLS
    path('', include('apps.core.urls')), # Homepage, dashboards
    path('auth/', include('apps.users.urls')), # Login, register, logout
    path('account/', include('apps.accounts.urls')), # Account management
    path('sources/', include('apps.sources.urls')), # Data sources management
    path('catalog/', include('apps.catalog.urls')), # Catalog of tables and columns
    path('insights/', include('apps.insights.urls')), # View/generate insights
]
