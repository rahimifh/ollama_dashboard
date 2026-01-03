from django.db import models

class ChatSession(models.Model):
    title = models.CharField(max_length=200, default="New chat")
    model = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.title} ({self.model})"


class ChatMessage(models.Model):
    ROLE_SYSTEM = "system"
    ROLE_USER = "user"
    ROLE_ASSISTANT = "assistant"
    ROLE_TOOL = "tool"

    ROLE_CHOICES = [
        (ROLE_SYSTEM, "system"),
        (ROLE_USER, "user"),
        (ROLE_ASSISTANT, "assistant"),
        (ROLE_TOOL, "tool"),
    ]

    session = models.ForeignKey(
        ChatSession, on_delete=models.CASCADE, related_name="messages"
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.role}: {self.content[:40]}"
