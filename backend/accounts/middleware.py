from django.utils import timezone
from django.utils import translation

class UserPreferencesMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            if request.user.timezone:
                timezone.activate(request.user.timezone)
            if request.user.language:
                translation.activate(request.user.language)
        return self.get_response(request)