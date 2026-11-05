
from src.inference_worker import ModelWorker


def main():
    worker = ModelWorker(timeout_seconds=5.0)

    try:
        worker.start()

        print("Worker ready:", worker.ready)

        result = worker.predict(
            "What is machine learning?"
        )

        print("Prediction:", result)

        if result["class_name"] != "BENIGN":
            raise RuntimeError(
                "Worker smoke test failed: unexpected prediction"
            )

        print("WORKER SMOKE TEST PASSED")

    finally:
        worker.stop()

    print("Worker stopped successfully")


if __name__ == "__main__":
    main()
