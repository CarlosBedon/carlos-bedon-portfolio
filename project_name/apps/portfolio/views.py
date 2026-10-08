from django.core.files.storage import default_storage
from django.views.generic import TemplateView

# Object key inside the media bucket (Supabase Storage in production).
DASHBOARD_PHOTO = "dashboard.jpg"


class DashboardView(TemplateView):
    template_name = "pages/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["photo_url"] = default_storage.url(DASHBOARD_PHOTO)
        return context


class PortfolioHomeView(TemplateView):
    template_name = "portfolio/home.html"
