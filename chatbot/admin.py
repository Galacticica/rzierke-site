"""
File: admin.py
Author: Reagan Zierke <reaganzierke@gmail.com>
Date: 2026-03-05
Description: Register chatbot models for the Django admin interface.
"""


from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from .models import AIModel, AIQuirk, Conversation, Message


class AIQuirkInline(TabularInline):
    model = AIModel.quirk.through
    extra = 1


@admin.register(AIModel)
class AIModelAdmin(ModelAdmin):
    list_display = ('name', 'description')
    inlines = [AIQuirkInline]


@admin.register(AIQuirk)
class AIQuirkAdmin(ModelAdmin):
    list_display = ('name', 'description')

@admin.register(Conversation)
class ConversationAdmin(ModelAdmin):
    list_display = ('id', 'user', 'created_at')
