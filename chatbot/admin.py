"""
File: admin.py
Author: Reagan Zierke <reaganzierke@gmail.com>
Date: 2026-03-05
Description: Register chatbot models for the Django admin interface.
"""


from django.contrib import admin
from .models import AIModel, AIQuirk, Conversation, Message


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

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'created_at')
