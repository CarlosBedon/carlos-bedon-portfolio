from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

from commerce.tenants.access import can_enter_store_admin


class StoreAdminAuthenticationForm(AuthenticationForm):
    """Login form for the merchant panel of ``request.store``.

    Unlike the platform admin form, it does not require ``is_staff``.
    The user needs an active membership in this store, or must be a
    superuser. A rejected login shows the same message as a wrong
    password, so the form does not reveal who belongs to the store.
    """

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        store = getattr(self.request, "store", None)
        if not can_enter_store_admin(user, store):
            raise ValidationError(
                self.error_messages["invalid_login"],
                code="invalid_login",
                params={"username": self.username_field.verbose_name},
            )
