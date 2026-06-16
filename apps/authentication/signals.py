"""Create a Profile automatically when a User is created."""
from django.contrib.auth.models import Permission
from django.db.models.signals import post_delete, post_migrate, post_save
from django.dispatch import receiver

from .models import Profile, User
from .permissions import invalidate_permission_matrix_cache


@receiver(post_save, sender=User)
def ensure_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)


@receiver(post_migrate)
def _invalidate_perm_matrix_on_migrate(sender, **kwargs):
    invalidate_permission_matrix_cache()


@receiver(post_save, sender=Permission)
@receiver(post_delete, sender=Permission)
def _invalidate_perm_matrix_on_permission_change(sender, **kwargs):
    invalidate_permission_matrix_cache()
