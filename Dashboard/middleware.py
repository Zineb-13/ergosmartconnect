from django.utils import timezone
import pytz

class TimezoneMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Forcer le fuseau horaire de l'Algérie
        algeria_tz = pytz.timezone('Africa/Algiers')
        timezone.activate(algeria_tz)
        
        response = self.get_response(request)
        
        # Ne pas désactiver le fuseau pour garder l'affichage correct
        return response