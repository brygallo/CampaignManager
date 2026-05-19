from apps.campaigns.active import visible_campaigns_queryset
from apps.campaigns.models import Campaign


def visible_campaign_choices(user):
    return visible_campaigns_queryset(Campaign.objects.all(), user).order_by("name")
