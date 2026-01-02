"""Utility classes for clip-cutter."""

import itertools
import threading
import time


class Spinner:
    """Animated spinner for long-running operations."""

    def __init__(self, message: str = ""):
        self.message = message
        self.running = False
        self.thread = None
        self.frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def _spin(self):
        for frame in itertools.cycle(self.frames):
            if not self.running:
                break
            print(f"\r{frame} {self.message}", end="", flush=True)
            time.sleep(0.1)

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._spin)
        self.thread.start()

    def stop(self, final_message: str = ""):
        self.running = False
        if self.thread:
            self.thread.join()
        # Clear the line and print final message
        print(f"\r{' ' * (len(self.message) + 5)}\r", end="")
        if final_message:
            print(final_message)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()


class ProgressBar:
    """Progress bar for operations with known duration."""

    def __init__(self, total: float, width: int = 30, prefix: str = ""):
        self.total = total
        self.width = width
        self.prefix = prefix
        self.current = 0

    def update(self, current: float):
        self.current = min(current, self.total)
        percent = self.current / self.total if self.total > 0 else 0
        filled = int(self.width * percent)
        bar = "█" * filled + "░" * (self.width - filled)
        percent_str = f"{percent * 100:5.1f}%"
        print(f"\r   {self.prefix}[{bar}] {percent_str}", end="", flush=True)

    def finish(self):
        self.update(self.total)
        print()
