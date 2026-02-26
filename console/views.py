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


from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST
from .models import ChatMessage, ChatSession, FineTuningJob
from .services import ollama, finetuning

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

#================================================ finetune 

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


# Fine-tuning views
from .models import FineTuningJob
from .services import finetuning


@require_GET
def finetune(request: HttpRequest) -> HttpResponse:
    """Fine-tuning dashboard page."""
    jobs = FineTuningJob.objects.all()
    
    # Get available models for base model selection
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
        "jobs": jobs,
        "available_models": available_models,
        "ollama_error": ollama_error,
    }
    return render(request, "console/finetune.html", ctx)


@require_POST
@csrf_protect
def finetune_create(request: HttpRequest) -> HttpResponse:
    """Create a new fine-tuning job."""
    name = (request.POST.get("name") or "").strip() or "Fine-tuned Model"
    base_model = (request.POST.get("base_model") or "").strip()
    epochs = int(request.POST.get("epochs", 3))
    learning_rate = float(request.POST.get("learning_rate", 0.0001))
    batch_size = int(request.POST.get("batch_size", 4))
    
    # Handle file upload
    dataset_file = request.FILES.get("dataset_file")
    if not dataset_file:
        return JsonResponse({"error": "No dataset file provided"}, status=400)
    
    if not base_model:
        return JsonResponse({"error": "No base model selected"}, status=400)
    
    # Save uploaded file temporarily
    import tempfile
    import os
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(dataset_file.name)[1]) as tmp_file:
        for chunk in dataset_file.chunks():
            tmp_file.write(chunk)
        dataset_path = tmp_file.name
    
    try:
        # Validate dataset
        dataset_size, errors = finetuning.validate_dataset_format(dataset_path)
        if errors:
            os.unlink(dataset_path)
            return JsonResponse({"error": "Dataset validation failed", "details": errors}, status=400)
        
        # Create job
        job = FineTuningJob.objects.create(
            name=name,
            base_model=base_model,
            epochs=epochs,
            learning_rate=learning_rate,
            batch_size=batch_size,
            dataset_file=dataset_path,
            dataset_size=dataset_size,
        )
        
        # Start fine-tuning in background
        finetuning.start_fine_tuning_job(job.id)
        
        return JsonResponse({
            "success": True,
            "job_id": job.id,
            "message": f"Fine-tuning job created successfully. Job ID: {job.id}"
        })
        
    except Exception as e:
        # Clean up temp file on error
        try:
            os.unlink(dataset_path)
        except OSError:
            pass
        return JsonResponse({"error": str(e)}, status=500)


@require_POST
@csrf_protect
def finetune_cancel(request: HttpRequest) -> HttpResponse:
    """Cancel a running fine-tuning job."""
    job_id = (request.POST.get("job_id") or "").strip()
    if not job_id:
        return JsonResponse({"error": "Missing job_id"}, status=400)
    
    try:
        job_id_int = int(job_id)
    except ValueError:
        return JsonResponse({"error": "Invalid job_id"}, status=400)
    
    success = finetuning.cancel_fine_tuning_job(job_id_int)
    
    if success:
        return JsonResponse({"success": True, "message": "Job cancelled successfully"})
    else:
        return JsonResponse({"error": "Failed to cancel job"}, status=400)


@require_GET
def finetune_progress(request: HttpRequest, job_id: int) -> StreamingHttpResponse:
    """Stream progress updates for a fine-tuning job."""
    def gen() -> Any:
        try:
            for update in finetuning.get_job_progress_stream(job_id):
                yield json.dumps(update) + "\n"
        except Exception as e:
            yield json.dumps({"error": str(e), "done": True}) + "\n"
    
    resp = StreamingHttpResponse(gen(), content_type="application/x-ndjson")
    resp["Cache-Control"] = "no-cache"
    return resp


@require_GET
def finetune_job_detail(request: HttpRequest, job_id: int) -> HttpResponse:
    """Get details of a specific fine-tuning job."""
    try:
        job = FineTuningJob.objects.get(pk=job_id)
    except FineTuningJob.DoesNotExist:
        return JsonResponse({"error": "Job not found"}, status=404)
    
    return JsonResponse({
        "id": job.id,
        "name": job.name,
        "base_model": job.base_model,
        "fine_tuned_model": job.fine_tuned_model,
        "status": job.status,
        "progress": job.progress_percentage,
        "current_epoch": job.current_epoch,
        "epochs": job.epochs,
        "current_step": job.current_step,
        "total_steps": job.total_steps,
        "loss": job.loss,
        "duration": job.duration,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "error_message": job.error_message,
    })


@require_POST
@csrf_protect
def finetune_delete(request: HttpRequest) -> HttpResponse:
    """Delete a fine-tuning job and associated model."""
    job_id = (request.POST.get("job_id") or "").strip()
    if not job_id:
        return JsonResponse({"error": "Missing job_id"}, status=400)
    
    try:
        job_id_int = int(job_id)
    except ValueError:
        return JsonResponse({"error": "Invalid job_id"}, status=400)
    
    try:
        job = FineTuningJob.objects.get(pk=job_id_int)
        
        # Delete the fine-tuned model if it exists
        if job.fine_tuned_model and job.status == FineTuningJob.STATUS_COMPLETED:
            try:
                ollama.delete_model(job.fine_tuned_model)
            except ollama.OllamaError:
                # Continue even if model deletion fails
                pass
        
        # Clean up dataset file
        if job.dataset_file:
            try:
                import os
                os.unlink(job.dataset_file)
            except OSError:
                pass
        
        # Delete the job
        job.delete()
        
        return JsonResponse({"success": True, "message": "Job deleted successfully"})
        
    except FineTuningJob.DoesNotExist:
        return JsonResponse({"error": "Job not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)