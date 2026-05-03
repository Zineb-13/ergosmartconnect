from django import template
from datetime import datetime, timedelta

register = template.Library()

# Fuseau horaire de l'Algérie (UTC+1)
ALGERIA_TZ_OFFSET = timedelta(hours=1)

@register.filter
def algeria_localtime(dt):
    """Convertit une datetime en heure locale Algérie (UTC+1)"""
    if dt is None:
        return ''
    
    try:
        # Ajouter 1 heure directement
        return dt + ALGERIA_TZ_OFFSET
    except Exception as e:
        print(f"Error in algeria_localtime: {e}")
        return dt

@register.simple_tag
def algeria_now():
    """Retourne l'heure actuelle en Algérie"""
    return datetime.now() + ALGERIA_TZ_OFFSET