'''
File: apps.py
Project: rzierke-site
Created Date: 2026-05-25
Author: Reagan Zierke
Email: reaganzierke@gmail.com
-----
Last Modified: 2026-05-25 19:19:31
Modified By: Reagan Zierke
-----
Description: App configuration for the connections app, including signal registration.
'''

from django.apps import AppConfig


class ConnectionsConfig(AppConfig):
    default = True
    name = 'connections'

    def ready(self):
        from . import signals  
