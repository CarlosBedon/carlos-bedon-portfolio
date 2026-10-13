from django.contrib.auth.mixins import AccessMixin
from django.contrib.auth.models import AnonymousUser
from django.http import Http404

from commerce.tenants.access import active_membership


class TenantRequiredMixin(AccessMixin):
    """Require an active membership in the store resolved for this request.

    A missing, inactive, or soft-deleted store is a 404. An anonymous
    user is sent to the login page. An authenticated user without an
    active membership, or without ``required_role``, is also a 404, so
    the response does not say whether the store exists. A Django
    superuser skips the membership check only after the store itself is
    valid. ``request.user.is_superuser`` is the flag Django sets; staff
    without that flag still need a membership.
    """

    required_role = None

    def dispatch(self, request, *args, **kwargs):
        store = getattr(request, "store", None)
        if not getattr(store, "is_publishable", False):
            raise Http404
        if not hasattr(request, "user"):
            request.user = AnonymousUser()
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if request.user.is_superuser:
            return super().dispatch(request, *args, **kwargs)
        if active_membership(request.user, store, role=self.required_role) is None:
            raise Http404
        return super().dispatch(request, *args, **kwargs)
