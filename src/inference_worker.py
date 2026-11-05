
import multiprocessing
from threading import Lock

from src.predict import load_model, predict


class WorkerUnavailable(RuntimeError):
    pass


class WorkerBusy(RuntimeError):
    pass


class WorkerTimeout(RuntimeError):
    pass


def worker_main(connection):
    # Загружаем проверенную модель один раз
    # при запуске дочернего процесса.
    try:
        model = load_model()
    except Exception:  # noqa: BLE001
        connection.send(("startup_error", None))
        connection.close()
        return

    try:
        connection.send(("ready", None))

        while True:
            try:
                message = connection.recv()
            except (EOFError, OSError):
                break

            if message is None:
                break

            command, text = message

            try:
                if command != "predict":
                    raise ValueError("Invalid worker command")

                result = predict(
                    {"text": text},
                    model=model,
                )
                response = ("ok", result)

            except Exception:  # noqa: BLE001
                response = ("error", None)

            try:
                connection.send(response)
            except (BrokenPipeError, EOFError, OSError):
                break
    finally:
        connection.close()


class ModelWorker:
    def __init__(self, timeout_seconds=5.0):
        self.timeout_seconds = timeout_seconds
        self.context = multiprocessing.get_context("spawn")
        self.lock = Lock()
        self.process = None
        self.connection = None

    @property
    def ready(self):
        return (
            self.process is not None
            and self.process.is_alive()
            and self.connection is not None
        )

    def _stop_locked(self):
        connection = self.connection
        process = self.process

        self.connection = None
        self.process = None

        if connection is not None:
            connection.close()

        if process is not None:
            if process.is_alive():
                process.terminate()
                process.join(timeout=1)

                if process.is_alive():
                    process.kill()
                    process.join(timeout=1)
            else:
                process.join(timeout=0)

            process.close()

    def start(self):
        with self.lock:
            if self.ready:
                return

            self._stop_locked()

            parent, child = self.context.Pipe()

            process = self.context.Process(
                target=worker_main,
                args=(child,),
                daemon=True,
            )

            try:
                process.start()
            except Exception:
                parent.close()
                child.close()
                raise

            child.close()

            self.process = process
            self.connection = parent

            try:
                if not parent.poll(15):
                    raise WorkerUnavailable(
                        "Worker startup timeout"
                    )

                status, _ = parent.recv()

                if status != "ready":
                    raise WorkerUnavailable(
                        "Worker initialization failed"
                    )

            except (
                WorkerUnavailable,
                EOFError,
                OSError,
            ) as exc:
                self._stop_locked()
                raise WorkerUnavailable(
                    "Worker startup failed"
                ) from exc

    def predict(self, text):
        # Один запрос одновременно на один worker.
        if not self.lock.acquire(blocking=False):
            raise WorkerBusy("Worker busy")

        try:
            if not self.ready:
                raise WorkerUnavailable(
                    "Worker not ready"
                )

            try:
                self.connection.send(("predict", text))

                if not self.connection.poll(
                    self.timeout_seconds
                ):
                    # Завершаем зависший процесс.
                    self._stop_locked()
                    raise WorkerTimeout(
                        "Inference timeout"
                    )

                status, result = self.connection.recv()

            except (BrokenPipeError, EOFError, OSError) as exc:
                self._stop_locked()
                raise WorkerUnavailable(
                    "Worker connection lost"
                ) from exc

            if status != "ok":
                raise WorkerUnavailable(
                    "Inference failed"
                )

            return result

        finally:
            self.lock.release()

    def stop(self):
        with self.lock:
            self._stop_locked()
