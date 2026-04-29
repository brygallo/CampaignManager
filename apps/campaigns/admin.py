from django.contrib import admin

from .models import Campaign, Candidate, Election, PoliticalMovement, Position

admin.site.register(Election)
admin.site.register(PoliticalMovement)
admin.site.register(Position)
admin.site.register(Candidate)
admin.site.register(Campaign)
