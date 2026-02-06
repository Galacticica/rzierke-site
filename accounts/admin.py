"""
File: admin.py
Author: Reagan Zierke <reaganzierke@gmail.com>
Date: 2026-02-05
Description: Registration of custom User model in admin.
"""


from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

admin.site.register(User)
