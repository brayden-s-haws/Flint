from __future__ import annotations

# TODO(stub): Import LoginRequiredMixin from django.contrib.auth.mixins
# TODO(stub): Import ListView, DetailView, View from django.views.generic
# TODO(stub): Import redirect, get_object_or_404 from django.shortcuts
# TODO(stub): Import HttpRequest, HttpResponse from django.http
# TODO(stub): Import Any from typing
# TODO(stub): Import TenantQuerysetMixin from apps.core.mixins
# TODO(stub): Import Insight, InsightPrompt from apps.insights.models
# TODO(stub): Import Table from apps.catalog.models
# TODO(stub): Import get_service from apps.insights.services.provider


# TODO(stub): InsightListView — class-based ListView
# - Inherit from: TenantQuerysetMixin, LoginRequiredMixin, ListView (in that order)
# - model = Insight
# - template_name = 'insights/insight_list.html'
# - context_object_name = 'insights'
# - Override get_queryset(self) -> QuerySet[Insight]
#   - Call super().get_queryset() to get the tenant-scoped base queryset
#   - Chain .select_related('insight_prompt') to avoid N+1 when displaying prompt name
#   - Return the queryset ordered by '-created_at' (newest first)
class InsightListView:
    pass


# TODO(stub): InsightDetailView — class-based DetailView
# - Inherit from: TenantQuerysetMixin, LoginRequiredMixin, DetailView (in that order)
# - model = Insight
# - template_name = 'insights/insight_detail.html'
# - No extra get_context_data needed for MVP — the Insight object is enough
#   (InsightTarget linking to a Table is available via insight.insighttarget_set if needed)
class InsightDetailView:
    pass


# TODO(stub): GenerateInsightView — plain View that handles POST only
# - Inherit from: LoginRequiredMixin, View
# - Do NOT use ListView/DetailView — this is an action view, not a display view
# - It receives a table_id from the URL (see urls.py: generate/<int:pk>/)
#   Note: the URL kwarg name in urls.py is 'pk' — access it via self.kwargs['pk']
#
# - Implement post(self, request: HttpRequest, pk: int) -> HttpResponse:
#   Step 1: Fetch the Table using get_object_or_404(Table, pk=pk, account=request.account)
#           - Filtering by account ensures tenant isolation (don't use TenantQuerysetMixin
#             here since we're not on a ListView/DetailView)
#
#   Step 2: Get the InsightPrompt to use
#           - For MVP: fetch the first active InsightPrompt for this account
#             e.g. InsightPrompt.objects.filter(account=request.account).first()
#           - If none exists, redirect back with an error message (use Django messages framework)
#             from django.contrib import messages; messages.error(request, "No prompt configured.")
#
#   Step 3: Call get_service(insight_prompt) to get the right LLM service instance
#
#   Step 4: Call service.generate_table_description(table) to get the generated text string
#           - This is a sync LLM call — it will block until the API responds
#           - Wrap in try/except Exception to catch API failures gracefully
#
#   Step 5: Create the Insight object
#           - Insight.objects.create(
#               account=request.account,
#               text=<generated text>,
#               insight_type='ai',
#               status='active',
#               insight_prompt=insight_prompt,
#             )
#
#   Step 6: Create the InsightTarget to link the Insight to the Table
#           - InsightTarget.objects.create(
#               account=request.account,
#               insight=insight,
#               target=table,
#             )
#
#   Step 7: Redirect to the table detail page
#           - Use redirect('catalog:detail', pk=table.pk)
#           - This returns the user to the table they generated the insight for
#
# - Do NOT implement a get() method — this view should only accept POST
#   If someone hits it with GET, Django's View base class will return 405 Method Not Allowed
class GenerateInsightView:
    pass