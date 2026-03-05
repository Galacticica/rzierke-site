from django.db import models

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
