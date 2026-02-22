from django.urls import path

from . import views

app_name = "console"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("chat/", views.chat, name="chat"),
    path("chat/new/", views.chat_new, name="chat_new"),
    path("chat/set-model/", views.chat_set_model, name="chat_set_model"),
    path("partials/status/", views.partial_status, name="partial_status"),
    path("partials/models/", views.partial_models, name="partial_models"),
    path("partials/running/", views.partial_running, name="partial_running"),
    path("models/delete/", views.model_delete, name="model_delete"),
    path("api/models/pull", views.api_models_pull, name="api_models_pull"),
    path("api/chat/stream", views.api_chat_stream, name="api_chat_stream"),
    # Test error pages (only accessible in DEBUG mode)
    path("test-errors/", views.test_errors, name="test_errors"),
    path("test-500/", views.test_500_error, name="test_500"),
    path("test-403/", views.test_403_error, name="test_403"),
    path("test-400/", views.test_400_error, name="test_400"),
]
