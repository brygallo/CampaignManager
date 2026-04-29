"""Wrapper around ``django-notifications-hq`` with success/info/warning/error levels."""
from notifications.signals import notify


class Notification:
    """Convenience wrapper modeled after ``sim.notifications.Notification``."""

    @classmethod
    def _send(cls, level, recipient, message, target=None, sender=None, send_email=False):
        actor = sender or recipient
        notify.send(
            sender=actor,
            actor=actor,
            recipient=recipient,
            verb=message,
            target=target,
            level=level,
        )

    @classmethod
    def success(cls, recipient, message, target=None, sender=None):
        cls._send("success", recipient, message, target=target, sender=sender)

    @classmethod
    def info(cls, recipient, message, target=None, sender=None):
        cls._send("info", recipient, message, target=target, sender=sender)

    @classmethod
    def warning(cls, recipient, message, target=None, sender=None):
        cls._send("warning", recipient, message, target=target, sender=sender)

    @classmethod
    def error(cls, recipient, message, target=None, sender=None):
        cls._send("error", recipient, message, target=target, sender=sender)
