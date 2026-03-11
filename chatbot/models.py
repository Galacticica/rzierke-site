"""
File: models.py
Author: Reagan Zierke <reaganzierke@gmail.com>
Date: 2026-03-05
Description: Models for chatbot conversations, messages, AI models, and quirks.
"""



from django.db import models
from django.utils import timezone

class Conversation(models.Model):
    '''A conversation between a user and the AI. Contains metadata and links to messages.'''
    title = models.CharField(max_length=255, blank=True, default="")
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='conversations')
    model = models.ForeignKey('chatbot.AIModel', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.title:
            created_time = self.created_at or timezone.now()
            self.title = f"Conversation {created_time.strftime('%Y-%m-%d %H:%M:%S')}"
        super().save(*args, **kwargs)

class Message(models.Model):
    '''A single message in a conversation, either from the user or the AI.'''
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.CharField(max_length=255)  
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.sender} at {self.timestamp}: {self.content[:50]}..."

class AIModel(models.Model):
    '''An AI model that can be used for conversations. Contains metadata and associated quirks.'''
    name = models.CharField(max_length=255)
    description = models.TextField()
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_ai_models',
    )
    quirk = models.ManyToManyField('AIQuirk', related_name='quirks', blank=True)
    
    def __str__(self):
        return self.name
    

class AIQuirk(models.Model):
    '''A quirk that can be associated with an AI model.'''
    name = models.CharField(max_length=255)
    description = models.TextField()
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_ai_quirks',
    )
    
    def __str__(self):
        return self.name
