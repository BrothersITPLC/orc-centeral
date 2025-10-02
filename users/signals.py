# from django.db.models.signals import post_delete, post_save, pre_save
# from django.dispatch import receiver

# from .models import CustomUser


# @receiver(pre_save, sender=CustomUser)
# def delete_old_profile_image(sender, instance, **kwargs):
#     """Delete old profile image if it's being replaced."""
#     if not instance.pk:  # new user, nothing to do
#         return

#     try:
#         old_instance = sender.objects.get(pk=instance.pk)
#     except sender.DoesNotExist:
#         return

#     old_image = old_instance.profile_image
#     new_image = instance.profile_image

#     if old_image and old_image != new_image:
#         old_image.delete(save=False)


# @receiver(post_delete, sender=CustomUser)
# def delete_profile_image_on_delete(sender, instance, **kwargs):
#     """Delete profile image when user is deleted."""
#     if instance.profile_image:
#         instance.profile_image.delete(save=False)


# # --- ROLE TO GROUP SYNC ---


# @receiver(post_save, sender=CustomUser)
# def sync_role_with_group(sender, instance, **kwargs):
#     """
#     Ensure user.groups is always synced with role.
#     """
#     instance.groups.clear()
#     if instance.role:
#         instance.groups.add(instance.role)

# workstation_app/users/signals.py

from django.conf import (  # Import settings to get AUTH_USER_MODEL if needed, though CustomUser is directly imported
    settings,
)
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from orcSync.models import ZoimeUserSyncStatus

from .models import CustomUser


@receiver(pre_save, sender=CustomUser)
def delete_old_profile_image(sender, instance, **kwargs):
    """Delete old profile image if it's being replaced."""
    if not instance.pk:
        return

    try:
        old_instance = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    old_image = old_instance.profile_image
    new_image = instance.profile_image

    if old_image and old_image != new_image:
        old_image.delete(save=False)


@receiver(post_delete, sender=CustomUser)
def delete_profile_image_on_delete(sender, instance, **kwargs):
    """Delete profile image when user is deleted."""
    if instance.profile_image:
        instance.profile_image.delete(save=False)


@receiver(post_save, sender=CustomUser)
def sync_role_with_group(sender, instance, **kwargs):
    """
    Ensure user.groups is always synced with role.
    """
    instance.groups.clear()
    if instance.role:
        instance.groups.add(instance.role)


@receiver(post_save, sender=CustomUser)
def create_zoime_sync_status_on_create(sender, instance, created, **kwargs):
    """
    Creates a ZoimeUserSyncStatus entry only when a CustomUser is first created.
    """
    if created:
        ZoimeUserSyncStatus.objects.get_or_create(user=instance)
        print(
            f"ZOIME_SYNC: Created ZoimeUserSyncStatus for new user {instance.username}"
        )
