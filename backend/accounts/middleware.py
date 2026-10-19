from django.utils import timezone

class UserPreferencesMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            if request.user.timezone:
                timezone.activate(request.user.timezone)
        return self.get_response(request)