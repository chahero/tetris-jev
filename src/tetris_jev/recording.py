"""Record the actual Pygame surface, including real inference waiting time."""

import shutil
import subprocess
import time
from pathlib import Path


class Recorder:
    def __init__(self, path: Path, size: tuple[int, int], fps: int = 30):
        executable = shutil.which("ffmpeg")
        if not executable:
            raise RuntimeError("FFmpeg is required for --record; add ffmpeg to PATH")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.fps = fps
        self.frames = 0
        self.started = None
        self.process = subprocess.Popen(
            [
                executable,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "rawvideo",
                "-pixel_format",
                "rgb24",
                "-video_size",
                f"{size[0]}x{size[1]}",
                "-framerate",
                str(fps),
                "-i",
                "-",
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(path),
            ],
            stdin=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW
            if hasattr(subprocess, "CREATE_NO_WINDOW")
            else 0,
        )

    def capture(self, surface):
        import pygame

        now = time.perf_counter()
        if self.started is None:
            self.started = now
        expected = int((now - self.started) * self.fps) + 1
        if expected > self.frames:
            pixels = pygame.image.tobytes(surface, "RGB")
            for _ in range(expected - self.frames):
                self.process.stdin.write(pixels)
                self.frames += 1

    def close(self):
        self.process.stdin.close()
        if self.process.wait(timeout=30) != 0:
            raise RuntimeError("FFmpeg failed to encode the recording")
