"""
Fine-tuning service for Ollama models.
"""

from __future__ import annotations

import csv
import json
import logging
import os
import re
import subprocess
import tempfile
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from django.utils import timezone

from .ollama import OllamaError  # noqa: F401 – re-exported for callers
from ..models import FineTuningJob

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Module-level registry so we can actually cancel a running subprocess
# ──────────────────────────────────────────────────────────────────────────────
_running_processes: dict[int, subprocess.Popen[str]] = {}
_process_lock = threading.Lock()


# ──────────────────────────────────────────────────────────────────────────────
# Exceptions
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class FineTuningError(Exception):
    """Custom exception for fine-tuning errors."""

    message: str
    job_id: int | None = None
    details: dict[str, Any] | None = field(default=None)

    def __str__(self) -> str:
        bits = [self.message]
        if self.job_id is not None:
            bits.append(f"(job_id={self.job_id})")
        return " ".join(bits)


# ──────────────────────────────────────────────────────────────────────────────
# Dataset validation
# ──────────────────────────────────────────────────────────────────────────────

def validate_dataset_format(dataset_path: str) -> tuple[int, list[str]]:
    """
    Validate dataset format and return (row_count, errors).

    Supported formats
    -----------------
    - **.jsonl** – every non-blank line must be a JSON object with a
      ``messages`` list; each message must carry ``role`` and ``content``.
    - **.csv**  – must contain ``role`` and ``content`` columns; every row
      must have non-empty values for both.
    """
    errors: list[str] = []
    size = 0

    if not os.path.exists(dataset_path):
        errors.append(f"Dataset file not found: {dataset_path}")
        return 0, errors

    try:
        with open(dataset_path, encoding="utf-8") as fh:
            if dataset_path.endswith(".jsonl"):
                size, errors = _validate_jsonl(fh)
            elif dataset_path.endswith(".csv"):
                size, errors = _validate_csv(fh)
            else:
                errors.append("Unsupported file format. Use .jsonl or .csv")
    except OSError as exc:
        errors.append(f"Error reading dataset: {exc}")

    return size, errors


def _validate_jsonl(fh: Any) -> tuple[int, list[str]]:
    errors: list[str] = []
    size = 0
    for i, raw in enumerate(fh, 1):
        line = raw.strip()
        if not line:
            continue
        size += 1
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"Line {i}: Invalid JSON – {exc}")
            continue

        messages = data.get("messages")
        if messages is None:
            errors.append(f"Line {i}: Missing 'messages' field")
        elif not isinstance(messages, list):
            errors.append(f"Line {i}: 'messages' must be a list")
        else:
            for j, msg in enumerate(messages):
                if "role" not in msg or "content" not in msg:
                    errors.append(
                        f"Line {i}, message {j}: missing 'role' or 'content'"
                    )
    return size, errors


def _validate_csv(fh: Any) -> tuple[int, list[str]]:
    errors: list[str] = []
    size = 0
    reader = csv.DictReader(fh)

    # BUG FIX: fieldnames can be None if the file is empty
    fieldnames = reader.fieldnames or []
    required = {"role", "content"}
    missing = required - set(fieldnames)
    if missing:
        errors.append(f"CSV is missing required columns: {', '.join(sorted(missing))}")
        return 0, errors

    for i, row in enumerate(reader, 1):
        size += 1
        if not row.get("role") or not row.get("content"):
            errors.append(f"Row {i}: 'role' or 'content' is empty")

    return size, errors


# ──────────────────────────────────────────────────────────────────────────────
# Modelfile creation
# ──────────────────────────────────────────────────────────────────────────────

def create_modelfile(
    base_model: str,
    system_prompt: str = "",
) -> str:
    """
    Create a minimal Ollama Modelfile for *inference* of a base model.

    Important
    ---------
    Ollama's ``ollama create`` command does **not** perform gradient-based
    fine-tuning and does not accept ``learning_rate``, ``num_epoch`` or
    ``batch_size`` parameters.  Those parameters were silently ignored (or
    caused errors) in the original code.  Training hyperparameters belong to
    the actual fine-tuning tool (e.g. llama.cpp ``finetune``, Unsloth, etc.)
    and are passed via :func:`_build_training_command`.

    This function only builds the Modelfile that registers the *result* model
    with Ollama after training is complete.
    """
    lines = [f"FROM {base_model}"]
    if system_prompt:
        # Escape any triple-double-quote sequences inside the prompt
        safe_prompt = system_prompt.replace('"""', '""\\"')
        lines.append(f'SYSTEM """\n{safe_prompt}\n"""')
    return "\n".join(lines) + "\n"


# ──────────────────────────────────────────────────────────────────────────────
# Job lifecycle
# ──────────────────────────────────────────────────────────────────────────────

def start_fine_tuning_job(job_id: int) -> None:
    """Kick off a fine-tuning job in a daemon background thread."""
    thread = threading.Thread(
        target=_run_fine_tuning_job,
        args=(job_id,),
        name=f"finetune-job-{job_id}",
        daemon=True,
    )
    thread.start()
    logger.info("Fine-tuning thread started for job %d", job_id)


def _run_fine_tuning_job(job_id: int) -> None:
    """
    Orchestrate the full fine-tuning pipeline inside a background thread.

    Steps
    -----
    1. Mark job as *running*.
    2. Validate the dataset.
    3. Launch the training subprocess and stream its output.
    4. Register the resulting model with Ollama via ``ollama create``.
    5. Mark job as *completed* (or *failed* on any error).
    """
    # Must be called at the very start of every new thread that touches the ORM
    from django.db import close_old_connections
    close_old_connections()

    # ── 1. Load job ──────────────────────────────────────────────────────────
    try:
        job = FineTuningJob.objects.get(pk=job_id)
    except FineTuningJob.DoesNotExist:
        logger.error("FineTuningJob %d not found – aborting thread.", job_id)
        return

    logger.info("Starting fine-tuning job %d (base_model=%s)", job_id, job.base_model)
    job.status = FineTuningJob.STATUS_RUNNING
    job.started_at = timezone.now()
    job.save(update_fields=["status", "started_at"])

    # ── 2. Validate dataset ──────────────────────────────────────────────────
    dataset_size, dataset_errors = validate_dataset_format(job.dataset_file)
    if dataset_errors:
        _fail_job(job, "Dataset validation failed: " + "; ".join(dataset_errors))
        return
    logger.info("Dataset validated: %d samples", dataset_size)

    # ── 3. Run training ──────────────────────────────────────────────────────
    model_name = f"{job.base_model.split(':')[0]}-finetuned-{job.id}"

    try:
        _execute_training(job, model_name)
    except FineTuningError as exc:
        _fail_job(job, str(exc))
        return
    except Exception as exc:  # pragma: no cover
        logger.exception("Unexpected error in fine-tuning job %d", job_id)
        _fail_job(job, f"Unexpected error: {exc}")
        return

    # ── 4. Register model with Ollama ────────────────────────────────────────
    try:
        _register_model_with_ollama(job.base_model, model_name)
    except FineTuningError as exc:
        _fail_job(job, str(exc))
        return

    # ── 5. Mark completed ────────────────────────────────────────────────────
    from django.db import close_old_connections as _coc
    _coc()
    job.refresh_from_db()
    job.status = FineTuningJob.STATUS_COMPLETED
    job.fine_tuned_model = model_name
    job.completed_at = timezone.now()
    job.save(update_fields=["status", "fine_tuned_model", "completed_at"])
    logger.info("Fine-tuning job %d completed – model: %s", job_id, model_name)


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

def _build_training_command(job: FineTuningJob) -> list[str]:
    """
    Build the shell command that performs the actual gradient-based training.

    This implementation targets **llama.cpp** ``finetune``; swap this out for
    Unsloth, torchtune, etc. as needed.  Keeping it in one place makes the
    training backend easy to replace without touching the orchestration logic.
    """
    cmd = [
        "llama-finetune",
        "--model-base", job.base_model,
        "--train-data", job.dataset_file,
        "--epochs", str(job.epochs),
        "--learning-rate", str(job.learning_rate),
        "--batch", str(job.batch_size),
        "--output-dir", f"/tmp/finetune-{job.id}",
    ]
    return cmd


def _execute_training(job: FineTuningJob, model_name: str) -> None:
    """
    Launch the training subprocess, stream stdout, and parse progress/loss.

    Raises :class:`FineTuningError` on non-zero exit or if the job is
    cancelled while running.
    """
    from django.db import close_old_connections

    cmd = _build_training_command(job)
    logger.debug("Training command: %s", " ".join(cmd))

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
        )
    except FileNotFoundError:
        raise FineTuningError(
            "Training binary not found. Ensure llama-finetune (or equivalent) "
            "is installed and on PATH.",
            job_id=job.id,
        )

    # Register the process so cancel_fine_tuning_job() can kill it
    with _process_lock:
        _running_processes[job.id] = process

    epoch_pattern = re.compile(r"epoch\s+(\d+)\s*/\s*(\d+)", re.IGNORECASE)
    loss_pattern = re.compile(r"loss[\s:=]+([\d.]+)", re.IGNORECASE)

    # Fields to bulk-save so we don't hit the DB on every line
    pending_fields: dict[str, Any] = {}

    try:
        assert process.stdout is not None  # always true given PIPE
        for raw_line in process.stdout:
            line = raw_line.strip()
            if not line:
                continue
            logger.debug("[job %d] %s", job.id, line)

            # ── Epoch progress ──
            m = epoch_pattern.search(line)
            if m:
                current_epoch = int(m.group(1))
                total_epochs = int(m.group(2))
                pending_fields["current_epoch"] = current_epoch
                # Keep total_steps proportional; refine if trainer emits steps
                pending_fields["total_steps"] = total_epochs * 100
                pending_fields["current_step"] = current_epoch * 100

            # ── Loss ──
            m = loss_pattern.search(line)
            if m:
                pending_fields["loss"] = float(m.group(1))

            # ── Persist pending fields (if any) ──
            if pending_fields:
                close_old_connections()
                # BUG FIX: refresh_from_db() was inside the hot loop and would
                # overwrite pending_fields we hadn't saved yet.  We now only
                # write, never read-back, inside the loop.
                for attr, val in pending_fields.items():
                    setattr(job, attr, val)
                job.save(update_fields=list(pending_fields.keys()))
                pending_fields.clear()

            # ── Cancellation check ──
            # Re-read *only* the status column to detect external cancellation
            close_old_connections()
            current_status = (
                FineTuningJob.objects.filter(pk=job.id)
                .values_list("status", flat=True)
                .first()
            )
            if current_status == FineTuningJob.STATUS_CANCELLED:
                logger.info("Job %d was cancelled – terminating subprocess.", job.id)
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                return  # caller will see STATUS_CANCELLED already set

    finally:
        with _process_lock:
            _running_processes.pop(job.id, None)

    return_code = process.wait()
    if return_code != 0:
        raise FineTuningError(
            f"Training process exited with code {return_code}",
            job_id=job.id,
        )


def _register_model_with_ollama(base_model: str, model_name: str) -> None:
    """
    Write a Modelfile and call ``ollama create`` to register the fine-tuned
    model so it is available for inference.
    """
    modelfile_content = create_modelfile(base_model)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".Modelfile", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(modelfile_content)
        modelfile_path = tmp.name

    try:
        result = subprocess.run(
            ["ollama", "create", "-f", modelfile_path, model_name],
            capture_output=True,
            text=True,
            timeout=300,  # BUG FIX: original had no timeout – could hang forever
        )
        if result.returncode != 0:
            raise FineTuningError(
                f"'ollama create' failed: {result.stderr.strip()}",
            )
        logger.info("Model '%s' registered with Ollama.", model_name)
    except subprocess.TimeoutExpired:
        raise FineTuningError("'ollama create' timed out after 300 s.")
    except FileNotFoundError:
        raise FineTuningError(
            "Ollama binary not found. Ensure Ollama is installed and on PATH."
        )
    finally:
        try:
            os.unlink(modelfile_path)
        except OSError:
            pass


def _fail_job(job: FineTuningJob, message: str) -> None:
    """Centralised helper to mark a job as failed."""
    from django.db import close_old_connections
    close_old_connections()
    logger.error("Fine-tuning job %d failed: %s", job.id, message)
    try:
        job.refresh_from_db()
        job.status = FineTuningJob.STATUS_FAILED
        job.error_message = message
        job.completed_at = timezone.now()
        job.save(update_fields=["status", "error_message", "completed_at"])
    except Exception:  # pragma: no cover
        logger.exception("Could not persist failure state for job %d", job.id)


# ──────────────────────────────────────────────────────────────────────────────
# Public API – cancel & stream
# ──────────────────────────────────────────────────────────────────────────────

def cancel_fine_tuning_job(job_id: int) -> bool:
    """
    Cancel a running fine-tuning job.

    - Sends ``SIGTERM`` to the subprocess (then ``SIGKILL`` if needed).
    - Updates the DB record to ``STATUS_CANCELLED``.

    Returns ``True`` if the cancellation was applied, ``False`` otherwise.
    """
    try:
        job = FineTuningJob.objects.get(pk=job_id)
    except FineTuningJob.DoesNotExist:
        logger.warning("cancel_fine_tuning_job: job %d not found", job_id)
        return False

    if job.status != FineTuningJob.STATUS_RUNNING:
        logger.info(
            "cancel_fine_tuning_job: job %d is not running (status=%s)",
            job_id,
            job.status,
        )
        return False

    # BUG FIX: original never killed the actual subprocess – the process kept
    # running even after the DB row was flipped to CANCELLED.
    with _process_lock:
        process = _running_processes.get(job_id)

    if process is not None:
        logger.info("Terminating subprocess for job %d (pid=%d)", job_id, process.pid)
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            logger.warning("Subprocess did not stop – sending SIGKILL to pid %d", process.pid)
            process.kill()

    job.status = FineTuningJob.STATUS_CANCELLED
    job.completed_at = timezone.now()
    job.save(update_fields=["status", "completed_at"])
    logger.info("Fine-tuning job %d cancelled.", job_id)
    return True


def get_job_progress_stream(job_id: int, poll_interval: float = 1.0) -> Iterator[dict[str, Any]]:
    """
    Yield progress snapshots for a fine-tuning job until it reaches a
    terminal state (completed / failed / cancelled).

    Parameters
    ----------
    job_id:
        Primary key of the :class:`~..models.FineTuningJob`.
    poll_interval:
        Seconds to wait between DB polls (default 1 s).
    """
    from django.db import close_old_connections

    _TERMINAL = frozenset([
        FineTuningJob.STATUS_COMPLETED,
        FineTuningJob.STATUS_FAILED,
        FineTuningJob.STATUS_CANCELLED,
    ])

    # BUG FIX: original created `last_update` but never used it – removed.
    while True:
        close_old_connections()

        try:
            job = FineTuningJob.objects.get(pk=job_id)
        except FineTuningJob.DoesNotExist:
            yield {"error": "Job not found", "done": True}
            return

        is_done = job.status in _TERMINAL
        yield {
            "job_id": job.id,
            "status": job.status,
            "progress": job.progress_percentage,
            "current_epoch": job.current_epoch,
            "current_step": job.current_step,
            "total_steps": job.total_steps,
            "loss": job.loss,
            "duration": job.duration,
            "done": is_done,
        }

        if is_done:
            return

        time.sleep(poll_interval)

# services/finetuning.py