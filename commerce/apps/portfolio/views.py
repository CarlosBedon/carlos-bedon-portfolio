from django.views.generic import TemplateView


class PortfolioHomeView(TemplateView):
    template_name = "portfolio/home.html"
