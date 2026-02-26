from django.db import models
from django.utils import timezone

class ChatSession(models.Model):
    title = models.CharField(max_length=200, default="New chat")
    model = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['model']),
        ]

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
        indexes = [
            models.Index(fields=['session', 'created_at']),
            models.Index(fields=['created_at']),
            models.Index(fields=['role']),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.role}: {self.content[:40]}"


class FineTuningJob(models.Model):
    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"
    
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_RUNNING, "Running"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]
    
    name = models.CharField(max_length=200, default="Fine-tuned Model")
    base_model = models.CharField(max_length=200)
    fine_tuned_model = models.CharField(max_length=200, blank=True)
    
    # Training configuration
    epochs = models.IntegerField(default=3)
    learning_rate = models.FloatField(default=0.0001)
    batch_size = models.IntegerField(default=4)
    
    # Dataset information
    dataset_file = models.CharField(max_length=500, blank=True)
    dataset_size = models.IntegerField(default=0)
    
    # Training progress
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    current_epoch = models.IntegerField(default=0)
    current_step = models.IntegerField(default=0)
    total_steps = models.IntegerField(default=0)
    loss = models.FloatField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    
    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['base_model']),
        ]
    
    def __str__(self) -> str:
        return f"{self.name} ({self.base_model} → {self.fine_tuned_model or 'pending'})"
    
    @property
    def progress_percentage(self) -> float:
        if self.total_steps == 0:
            return 0.0
        return (self.current_step / self.total_steps) * 100
    
    @property
    def duration(self) -> float:
        if not self.started_at:
            return 0.0
        end_time = self.completed_at or timezone.now()
        return (end_time - self.started_at).total_seconds()
