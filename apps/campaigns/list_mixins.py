from apps.campaigns.active import visible_campaigns_queryset


class VisibleCampaignsMixin:
    """Hide inactive/historical campaigns unless the user has the explicit permission."""

    def get_queryset(self):
        queryset = super().get_queryset()
        return visible_campaigns_queryset(queryset, self.request.user)
