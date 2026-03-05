from django.contrib import admin
from .models import AIModel, AIQuirk


class AIQuirkInline(admin.TabularInline):
    model = AIModel.quirk.through
    extra = 1


@admin.register(AIModel)
class AIModelAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    inlines = [AIQuirkInline]


@admin.register(AIQuirk)
class AIQuirkAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
