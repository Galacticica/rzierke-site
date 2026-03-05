from django.db import models
from django.utils import timezone

class Conversation(models.Model):
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
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.CharField(max_length=255)  
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.sender} at {self.timestamp}: {self.content[:50]}..."

class AIModel(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    quirk = models.ManyToManyField('AIQuirk', related_name='quirks', blank=True)
    
    def __str__(self):
        return self.name
    

class AIQuirk(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    
    def __str__(self):
        return self.name
