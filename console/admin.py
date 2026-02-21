from django.contrib import admin
from .models import ChatSession, ChatMessage

# Register your models here.

admin.site.register(ChatMessage)
admin.site.register(ChatSession)