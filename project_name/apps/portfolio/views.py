from django.views.generic import TemplateView

# Public object. The S3 backend stays off unless every AWS_* variable is set,
# and then default_storage.url() would point at /media/ on this site.
DASHBOARD_PHOTO_URL = "https://yxuztraghlbanfgcfoym.supabase.co/storage/v1/object/public/media/dashboard.jpg"


class DashboardView(TemplateView):
    template_name = "pages/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["photo_url"] = DASHBOARD_PHOTO_URL
        return context


class PortfolioHomeView(TemplateView):
    template_name = "portfolio/home.html"
