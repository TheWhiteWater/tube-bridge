"""Process-local nearest-deadline worker for disposable-demo corpus expiry."""

import threading
import time
from collections.abc import Callable

from . import corpus
from . import demo_policy


_TRANSIENT_RETRY_SECONDS = 0.1


class DemoTTLWorker:
    """Wait for the nearest persisted deadline and purge at that deadline."""

    def __init__(self, clock: Callable[[], float] = time.time):
        self._clock = clock
        self._wake_event = threading.Event()
        self._stop_event = threading.Event()
        self._state_lock = threading.Lock()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        with self._state_lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._wake_event.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="tube-bridge-demo-ttl",
                daemon=True,
            )
            self._thread.start()

    def wake(self) -> None:
        self._wake_event.set()

    def stop(self, timeout: float = 2) -> bool:
        with self._state_lock:
            thread = self._thread
            if thread is None:
                return True
            self._stop_event.set()
            self._wake_event.set()
        thread.join(timeout)
        stopped = not thread.is_alive()
        if stopped:
            with self._state_lock:
                if self._thread is thread:
                    self._thread = None
        return stopped

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                deadline = corpus.next_demo_expiry()
                timeout = None if deadline is None else max(0.0, deadline - self._clock())
                was_woken = self._wake_event.wait(timeout)
                self._wake_event.clear()
                if self._stop_event.is_set():
                    return
                if was_woken:
                    continue
                corpus.delete_expired_demo_corpora(now=self._clock())
            except Exception:
                # Transient SQLite/filesystem errors must not silently disable
                # process-lifetime expiry enforcement. Retry without logging
                # client data, and remain immediately stoppable.
                if self._stop_event.wait(_TRANSIENT_RETRY_SECONDS):
                    return
                self._wake_event.clear()


_worker = DemoTTLWorker()


def start_demo_ttl_worker() -> None:
    # Transport invokes this entrypoint only in explicit demo mode. Keeping the
    # entrypoint self-contained makes startup ordering deterministic and testable.
    corpus.reconcile_demo_corpora()
    _worker.start()


def stop_demo_ttl_worker() -> bool:
    return _worker.stop(timeout=2)


def wake_demo_ttl_worker() -> None:
    if demo_policy.is_demo_mode():
        _worker.wake()
