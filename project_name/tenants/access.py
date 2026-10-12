from project_name.tenants.models import Store
from project_name.tenants.models import StoreMembership


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
