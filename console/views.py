import json
from typing import Any

from django.conf import settings
from django.db import close_old_connections
from django.http import (
    HttpRequest,
    HttpResponse,
    JsonResponse,
    StreamingHttpResponse,
)
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.core.exceptions import PermissionDenied, BadRequest

from .models import ChatMessage, ChatSession
from .services import ollama


# Error handlers
def handler404(request: HttpRequest, exception=None) -> HttpResponse:
    """Custom 404 error handler."""
    return render(request, 'console/404.html', status=404)


def handler500(request: HttpRequest) -> HttpResponse:
    """Custom 500 error handler."""
    return render(request, 'console/500.html', status=500)


def handler403(request: HttpRequest, exception=None) -> HttpResponse:
    """Custom 403 error handler."""
    return render(request, 'console/403.html', status=403)


def handler400(request: HttpRequest, exception=None) -> HttpResponse:
    """Custom 400 error handler."""
    return render(request, 'console/400.html', status=400)


# Test views for error pages (only in debug mode)
@require_GET
def test_errors(request: HttpRequest) -> HttpResponse:
    """Test page for error pages."""
    if not settings.DEBUG:
        return redirect('console:dashboard')
    return render(request, 'console/test_errors.html')


@require_GET
def test_500_error(request: HttpRequest) -> HttpResponse:
    """Trigger a 500 error for testing."""
    if not settings.DEBUG:
        return redirect('console:dashboard')
    # Raise an exception to trigger the 500 error page
    raise Exception("This is a test exception for the 500 error page")


@require_GET
def test_403_error(request: HttpRequest) -> HttpResponse:
    """Trigger a 403 error for testing."""
    if not settings.DEBUG:
        return redirect('console:dashboard')
    raise PermissionDenied("This is a test permission denied error")


@require_GET
def test_400_error(request: HttpRequest) -> HttpResponse:
    """Trigger a 400 error for testing."""
    if not settings.DEBUG:
        return redirect('console:dashboard')
    raise BadRequest("This is a test bad request error")


def _get_dashboard_context() -> dict[str, Any]:
    ctx: dict[str, Any] = {
        "ollama_base_url": getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434"),
        "ollama_version": None,
        "models": [],
        "running_models": [],
        "error": None,
        "error_details": None,
    }

    try:
        ctx["ollama_version"] = ollama.get_version()
        ctx["models"] = ollama.list_models().get("models", [])
        ctx["running_models"] = ollama.list_running_models().get("models", [])
    except ollama.OllamaError as e:
        ctx["error"] = str(e)
        ctx["error_details"] = e.details
    return ctx


@require_GET
def dashboard(request: HttpRequest) -> HttpResponse:
    return render(request, "console/dashboard.html", _get_dashboard_context())


def _default_chat_model() -> str:
    fallback = "llama3.2:latest"
    try:
        models = ollama.list_models().get("models", [])
        if models:
            name = models[0].get("name")
            if name:
                return str(name)
    except ollama.OllamaError:
        pass
    return fallback


@require_GET
def chat(request: HttpRequest) -> HttpResponse:
    sessions = list(ChatSession.objects.all())

    selected: ChatSession | None = None
    session_id = (request.GET.get("session") or "").strip()
    if session_id:
        selected = ChatSession.objects.filter(pk=session_id).first()
    if selected is None and sessions:
        selected = sessions[0]

    if selected is None:
        selected = ChatSession.objects.create(model=_default_chat_model(), title="New chat")
        sessions = [selected]

    messages = list(selected.messages.all())

    available_models: list[str] = []
    ollama_error: str | None = None
    try:
        available_models = [
            str(m.get("name"))
            for m in ollama.list_models().get("models", [])
            if m.get("name")
        ]
    except ollama.OllamaError as e:
        ollama_error = str(e)

    ctx: dict[str, Any] = {
        "sessions": sessions,
        "selected_session": selected,
        "messages": messages,
        "available_models": available_models,
        "ollama_error": ollama_error,
    }
    return render(request, "console/chat.html", ctx)


@require_POST
@csrf_protect
def chat_new(request: HttpRequest) -> HttpResponse:
    model = (request.POST.get("model") or "").strip() or _default_chat_model()
    title = (request.POST.get("title") or "").strip() or "New chat"
    session = ChatSession.objects.create(model=model, title=title)
    return redirect(f"{reverse('console:chat')}?session={session.pk}")


@require_POST
@csrf_protect
def chat_set_model(request: HttpRequest) -> HttpResponse:
    session_id = (request.POST.get("session_id") or "").strip()
    model = (request.POST.get("model") or "").strip()
    if not session_id or not model:
        return redirect("console:chat")

    session = ChatSession.objects.filter(pk=session_id).first()
    if session is None:
        return redirect("console:chat")

    session.model = model
    session.save(update_fields=["model"])
    return redirect(f"{request.META.get('HTTP_REFERER', '/chat/').split('#')[0]}")


@require_GET
def partial_status(request: HttpRequest) -> HttpResponse:
    ctx = _get_dashboard_context()
    return render(request, "console/_status.html", ctx)


@require_GET
def partial_models(request: HttpRequest) -> HttpResponse:
    ctx = _get_dashboard_context()
    return render(request, "console/_models_table.html", ctx)


@require_GET
def partial_running(request: HttpRequest) -> HttpResponse:
    ctx = _get_dashboard_context()
    return render(request, "console/_running_table.html", ctx)


@require_POST
@csrf_protect
def model_delete(request: HttpRequest) -> HttpResponse:
    model = (request.POST.get("model") or "").strip()
    if not model:
        return JsonResponse({"error": "Missing model"}, status=400)

    try:
        ollama.delete_model(model)
    except ollama.OllamaError as e:
        ctx = _get_dashboard_context()
        ctx["error"] = str(e)
        ctx["error_details"] = e.details
        return render(request, "console/_models_table.html", ctx, status=502)

    ctx = _get_dashboard_context()
    return render(request, "console/_models_table.html", ctx)


def _request_data(request: HttpRequest) -> dict[str, Any]:
    if request.content_type and request.content_type.startswith("application/json"):
        try:
            return json.loads(request.body or b"{}")
        except json.JSONDecodeError:
            return {}
    return dict(request.POST.items())


@require_POST
@csrf_protect
def api_models_pull(request: HttpRequest) -> StreamingHttpResponse:
    data = _request_data(request)
    model = str(data.get("model", "")).strip()
    if not model:
        return StreamingHttpResponse(
            iter([json.dumps({"error": "Missing model"}) + "\n"]),
            content_type="application/x-ndjson",
            status=400,
        )

    def gen() -> Any:
        try:
            for obj in ollama.pull_model_stream(model):
                yield json.dumps(obj) + "\n"
        except ollama.OllamaError as e:
            yield json.dumps({"error": str(e), "details": e.details}) + "\n"

    resp = StreamingHttpResponse(gen(), content_type="application/x-ndjson")
    resp["Cache-Control"] = "no-cache"
    return resp


@require_POST
@csrf_protect
def api_chat_stream(request: HttpRequest) -> StreamingHttpResponse:
    data = _request_data(request)
    session_id = str(data.get("session_id", "")).strip()
    content = str(data.get("content", "")).strip()

    if not session_id or not content:
        return StreamingHttpResponse(
            iter([json.dumps({"error": "Missing session_id or content", "done": True}) + "\n"]),
            content_type="application/x-ndjson",
            status=400,
        )

    session = ChatSession.objects.filter(pk=session_id).first()
    if session is None:
        return StreamingHttpResponse(
            iter([json.dumps({"error": "Unknown session", "done": True}) + "\n"]),
            content_type="application/x-ndjson",
            status=404,
        )

    # Persist user message immediately.
    ChatMessage.objects.create(session=session, role=ChatMessage.ROLE_USER, content=content)

    # Build message history from DB in order.
    history = [
        {"role": m.role, "content": m.content} for m in session.messages.all()
    ]

    def gen() -> Any:
        close_old_connections()
        assistant_parts: list[str] = []
        try:
            for chunk in ollama.chat_stream(model=session.model, messages=history):
                msg = chunk.get("message") or {}
                delta = msg.get("content") or ""
                if delta:
                    assistant_parts.append(str(delta))
                    yield json.dumps({"delta": str(delta), "done": False}) + "\n"

                if chunk.get("done"):
                    break

            assistant_text = "".join(assistant_parts)
            if assistant_text.strip():
                close_old_connections()
                ChatMessage.objects.create(
                    session=session,
                    role=ChatMessage.ROLE_ASSISTANT,
                    content=assistant_text,
                )

                if session.title == "New chat":
                    title = content.splitlines()[0].strip()[:80]
                    if title:
                        session.title = title
                        session.save(update_fields=["title"])

            yield json.dumps({"done": True}) + "\n"
        except ollama.OllamaError as e:
            yield json.dumps({"error": str(e), "details": e.details, "done": True}) + "\n"

    resp = StreamingHttpResponse(gen(), content_type="application/x-ndjson")
    resp["Cache-Control"] = "no-cache"
    return resp
