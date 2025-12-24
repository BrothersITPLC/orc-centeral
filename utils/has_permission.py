# def has_custom_permission(view, model):
#     action_permissions = {
#         "create": f"add_{model}",
#         "list": f"view_{model}",
#         "update": f"change_{model}",
#         "partial_update": f"change_{model}",
#         "destroy": f"delete_{model}",
#         "retrieve": f"view_{model}",
#     }
#     view.permission_required = action_permissions.get(view.action, None)
#     return [permission() for permission in view.permission_classes]


def has_custom_permission(view, model):
    """
    Dynamically sets permission_required based on the view's action or HTTP method.
    Compatible with:
    - DRF ViewSet
    - DRF ModelViewSet
    - DRF APIView
    """

    # Map DRF actions and HTTP methods to permission codenames
    permission_map = {
        # ViewSet / ModelViewSet actions
        "create": f"add_{model}",
        "list": f"view_{model}",
        "retrieve": f"view_{model}",
        "update": f"change_{model}",
        "partial_update": f"change_{model}",
        "destroy": f"delete_{model}",
        # APIView HTTP methods
        "post": f"add_{model}",
        "get": f"view_{model}",
        "put": f"change_{model}",
        "patch": f"change_{model}",
        "delete": f"delete_{model}",
    }

    # Determine action:
    # - For ViewSet/ModelViewSet → use .action
    # - For APIView → use HTTP method
    action_name = getattr(view, "action", None)
    if not action_name:
        # fallback for APIView or when action is not set
        action_name = view.request.method.lower()

    # Set the correct permission code dynamically
    permission_code = permission_map.get(action_name)
    view.permission_required = permission_code

    # Instantiate and return permission classes
    return [permission() for permission in view.permission_classes]
