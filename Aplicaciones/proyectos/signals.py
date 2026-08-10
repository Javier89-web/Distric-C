from django.contrib.auth.signals import user_logged_in
from django.contrib.sessions.models import Session
from django.dispatch import receiver
from .models import UserSession

@receiver(user_logged_in)
def enforce_single_session(sender, user, request, **kwargs):
    # Asegura que exista una session_key
    if not request.session.session_key:
        request.session.save()

    current_key = request.session.session_key

    obj, _ = UserSession.objects.get_or_create(user=user)
    old_key = obj.session_key

    # Si había otra sesión distinta, se elimina
    if old_key and old_key != current_key:
        Session.objects.filter(session_key=old_key).delete()

    obj.session_key = current_key
    obj.save()
