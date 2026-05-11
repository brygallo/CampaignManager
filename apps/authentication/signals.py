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


# Drop the cached permission-matrix skeleton whenever the underlying
# Permission rows might have changed. ``post_migrate`` covers the normal
# path (Django auto-creates Permissions for each ContentType after
# migrations); the Permission post_save/post_delete handlers cover manual
# edits via the Django admin, which don't fire post_migrate.
@receiver(post_migrate)
def _invalidate_perm_matrix_on_migrate(sender, **kwargs):
    invalidate_permission_matrix_cache()


@receiver(post_save, sender=Permission)
@receiver(post_delete, sender=Permission)
def _invalidate_perm_matrix_on_permission_change(sender, **kwargs):
    invalidate_permission_matrix_cache()
