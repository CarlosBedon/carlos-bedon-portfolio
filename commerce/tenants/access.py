"""Who can see or manage a store.

Views and APIs call these helpers themselves. Nothing in the ORM applies
them automatically. String helpers and the current request store live in
``utils.py``.
"""

from enum import StrEnum

from commerce.tenants.models import Store
from commerce.tenants.models import StoreMembership


class StoreArea(StrEnum):
    """Part of a store that the merchant panel exposes."""

    CATALOG = "catalog"
    STOCK = "stock"
    ORDERS = "orders"
    PAYMENTS = "payments"


class StoreAction(StrEnum):
    VIEW = "view"
    ADD = "add"
    CHANGE = "change"
    DELETE = "delete"


_ALL_ACTIONS = frozenset(StoreAction)
_EDIT_ACTIONS = frozenset({StoreAction.VIEW, StoreAction.ADD, StoreAction.CHANGE})
_VIEW_CHANGE = frozenset({StoreAction.VIEW, StoreAction.CHANGE})

# An area missing from a role means no access. Payments are only read in
# the merchant panel; the payment provider writes them.
ROLE_PERMISSIONS: dict[str, dict[StoreArea, frozenset[StoreAction]]] = {
    StoreMembership.Role.ADMIN: {
        StoreArea.CATALOG: _ALL_ACTIONS,
        StoreArea.STOCK: _ALL_ACTIONS,
        StoreArea.ORDERS: _VIEW_CHANGE,
        StoreArea.PAYMENTS: frozenset({StoreAction.VIEW}),
    },
    StoreMembership.Role.COLLABORATOR: {
        StoreArea.CATALOG: _EDIT_ACTIONS,
        StoreArea.STOCK: _EDIT_ACTIONS,
        StoreArea.ORDERS: _VIEW_CHANGE,
    },
}


def stores_for_member(user):
    """Return stores visible to this member.

    The queryset includes active and inactive stores linked by an active
    membership, and excludes soft-deleted stores. A superuser or staff
    user without a membership gets an empty queryset. Django Admin keeps
    using the unscoped manager. Views, APIs, and other queries must call
    this helper themselves; nothing applies it automatically.
    """
    if not getattr(user, "is_authenticated", False):
        return Store.objects.none()
    return Store.objects.filter(
        deleted_at__isnull=True,
        memberships__user=user,
        memberships__is_active=True,
    ).distinct()


def get_store_for_member(user, store_id: int) -> Store:
    """Return the member's store, or raise ``Store.DoesNotExist``.

    An unknown id, another store's id, an inactive membership, and a
    soft-deleted store all raise the same exception.
    """
    return stores_for_member(user).get(pk=store_id)


def active_membership(user, store: Store, *, role: str | None = None):
    """Return this user's active membership for ``store``, or ``None``.

    An anonymous user, an inactive membership, and a different role when
    ``role`` is set all return ``None``. A superuser without a membership
    also returns ``None``. This function does not decide whether a view
    may let that superuser through.
    """
    if not getattr(user, "is_authenticated", False):
        return None
    filters = {"store": store, "user": user, "is_active": True}
    if role is not None:
        filters["role"] = role
    try:
        return StoreMembership.objects.get(**filters)
    except StoreMembership.DoesNotExist:
        return None


def can_enter_store_admin(user, store: Store | None) -> bool:
    """Return whether this user may open the merchant panel of ``store``.

    The store must be active and not soft-deleted. Members need an active
    membership in that store. A superuser without one enters in read-only
    support mode; ``is_staff`` alone grants nothing.
    """
    if not _store_admin_user_ok(user, store):
        return False
    return user.is_superuser or active_membership(user, store) is not None


def store_admin_allows(request, area: StoreArea, action: StoreAction) -> bool:
    """Return whether the request user may do ``action`` on ``area``.

    An active membership in ``request.store`` decides through
    ``ROLE_PERMISSIONS``, even for a superuser. A superuser without a
    membership may only view. The membership is read once per request.
    """
    user = getattr(request, "user", None)
    store = getattr(request, "store", None)
    if not _store_admin_user_ok(user, store):
        return False
    membership = _request_membership(request)
    if membership is not None:
        allowed = ROLE_PERMISSIONS.get(membership.role, {}).get(area, frozenset())
        return action in allowed
    return user.is_superuser and action == StoreAction.VIEW


_NOT_LOADED = object()


def _request_membership(request):
    membership = getattr(request, "store_membership", _NOT_LOADED)
    if membership is _NOT_LOADED:
        membership = active_membership(request.user, request.store)
        request.store_membership = membership
    return membership


def _store_admin_user_ok(user, store: Store | None) -> bool:
    if store is None or not store.is_publishable:
        return False
    return bool(getattr(user, "is_authenticated", False) and user.is_active)


def user_can_manage_store(user, store: Store) -> bool:
    """Return whether this member can manage this store.

    The store must be active and not soft-deleted, and the user needs an
    active administrator membership. A superuser without that membership
    cannot manage it through this function. Views and APIs must call this
    function themselves. ``Store.is_publishable`` is a separate predicate
    and does not apply this check.
    """
    if store.deleted_at is not None or store.status != Store.Status.ACTIVE:
        return False
    if not getattr(user, "is_authenticated", False):
        return False
    return StoreMembership.objects.filter(
        store=store,
        user=user,
        is_active=True,
        role=StoreMembership.Role.ADMIN,
    ).exists()
