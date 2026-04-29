"""Forms para Site, Domain, SiteMembership."""
from superadmin.forms import ModelForm

from .models import Domain, Site, SiteMembership


class SiteForm(ModelForm):
    class Meta:
        model = Site
        fieldsets = {
            "Información del sitio": (
                ("name", "slug"),
                ("brand_color", "logo"),
                ("timezone", "currency"),
                ("description",),
            ),
        }


class DomainForm(ModelForm):
    class Meta:
        model = Domain
        fieldsets = {
            "Dominio": (
                ("site", "host"),
                ("is_primary",),
            ),
        }


class SiteMembershipForm(ModelForm):
    class Meta:
        model = SiteMembership
        fieldsets = {
            "Membresía": (
                ("user", "site"),
                ("role",),
            ),
        }
