from superadmin.decorators import register

from core.base import BaseSite
from core.list_mixins import DropdownFilterMixin

from .models import Canton, Parish, Province, Sector


@register("locations.Province")
class ProvinceSite(BaseSite):
    list_mixins = (DropdownFilterMixin,)
    list_fields = ("code", "name", "is_active:Activo")
    detail_fields = (("code", "name"), ("is_active",))
    search_params = ("code__icontains", "name__icontains")
    filter_fields = ("is_active:Activo",)


@register("locations.Canton")
class CantonSite(BaseSite):
    list_mixins = (DropdownFilterMixin,)
    list_fields = ("code", "name", "province", "is_active:Activo")
    detail_fields = (("code", "name"), ("province", "is_active"))
    search_params = ("code__icontains", "name__icontains", "province__name__icontains")
    filter_fields = ("province:Provincia", "is_active:Activo")


@register("locations.Parish")
class ParishSite(BaseSite):
    list_mixins = (DropdownFilterMixin,)
    list_fields = ("code", "name", "canton", "kind", "is_active:Activo")
    detail_fields = (("code", "name"), ("canton", "kind"), ("is_active",))
    search_params = ("code__icontains", "name__icontains", "canton__name__icontains")
    filter_fields = ("canton:Cantón", "kind:Tipo", "is_active:Activo")


@register("locations.Sector")
class SectorSite(BaseSite):
    list_mixins = (DropdownFilterMixin,)
    list_fields = ("name", "parish", "is_active:Activo")
    detail_fields = (("name", "parish"), ("is_active",))
    search_params = ("name__icontains", "parish__name__icontains")
    filter_fields = ("parish:Parroquia", "is_active:Activo")
