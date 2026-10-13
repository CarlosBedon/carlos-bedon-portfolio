def current_store(request):
    """Expose the store resolved for this request.

    The tenant middleware sets ``request.store``. Admin, collected static
    files, and any other request that skips that middleware have no
    attribute, so templates receive ``None`` instead of an error.
    """
    return {"current_store": getattr(request, "store", None)}
