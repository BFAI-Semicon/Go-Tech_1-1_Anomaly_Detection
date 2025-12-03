"""LeadersBoard Worker - Main entry point."""

import logging
import sys
import signal
import threading
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)

_stop_event = threading.Event()


def _handle_signal(signal_number, _frame) -> None:
    """Signal handler to gracefully stop the worker loop."""
    logger.info("Received signal %s; shutting down...", signal_number)
    _stop_event.set()


def main() -> None:
    """Worker main entry point."""
    logger.info("LeadersBoard Worker starting...")
    logger.info("Worker is ready; waiting for jobs...")

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    # Temporary idle loop to keep the container alive until the full
    # job worker implementation (queue consumer) is wired in.
    # This loop blocks efficiently and exits on SIGTERM/SIGINT.
    try:
        while not _stop_event.is_set():
            # Sleep in short intervals to respond promptly to stop requests
            time.sleep(1.0)
    finally:
        logger.info("Worker stopped.")


if __name__ == "__main__":
    main()
