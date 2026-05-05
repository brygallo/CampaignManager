from django.contrib import admin

from .models import Canton, Parish, Province, Sector


@admin.register(Province)
class ProvinceAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")
    search_fields = ("code", "name")
    list_filter = ("is_active",)


@admin.register(Canton)
class CantonAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "province", "is_active")
    search_fields = ("code", "name", "province__name")
    list_filter = ("province", "is_active")
    autocomplete_fields = ("province",)


@admin.register(Parish)
class ParishAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "canton", "kind", "is_active")
    search_fields = ("code", "name", "canton__name", "canton__province__name")
    list_filter = ("kind", "canton__province", "is_active")
    autocomplete_fields = ("canton",)


@admin.register(Sector)
class SectorAdmin(admin.ModelAdmin):
    list_display = ("name", "parish", "is_active")
    search_fields = ("name", "parish__name", "parish__canton__name")
    list_filter = ("parish__canton__province", "is_active")
    autocomplete_fields = ("parish",)
