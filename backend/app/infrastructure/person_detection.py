"""Continuous RTSP person recognition backed by a local YOLO model."""

import asyncio
import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from ..application.camera_service import CameraService
from .settings import settings


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PersonDetection:
    camera_id: int
    person_count: int
    detected_at: datetime


class PersonRecognitionService:
    def __init__(self, camera_service: CameraService):
        self._camera_service = camera_service
        self._detections: dict[int, PersonDetection] = {}
        self._lock = threading.Lock()
        self._model_lock = threading.Lock()
        self._model: object | None = None
        self._stop_event = threading.Event()
        self._tasks: list[asyncio.Task[None]] = []

    async def start(self) -> None:
        if not settings.person_detection_enabled:
            logger.info("Person detection is disabled")
            return
        try:
            await asyncio.to_thread(self._load_model)
        except Exception:
            logger.exception("Could not load person detection model")
            return
        sources = await self._camera_service.list_detection_sources()
        self._stop_event.clear()
        self._tasks = [
            asyncio.create_task(asyncio.to_thread(self._analyze_source, camera_id, source))
            for camera_id, source in sources.items()
        ]

    async def stop(self) -> None:
        self._stop_event.set()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    def detections_for(self, camera_ids: set[int] | None) -> list[PersonDetection]:
        cutoff = datetime.now(timezone.utc).timestamp() - settings.person_detection_alert_seconds
        with self._lock:
            return [
                detection for camera_id, detection in self._detections.items()
                if detection.detected_at.timestamp() >= cutoff
                and (camera_ids is None or camera_id in camera_ids)
            ]

    def _analyze_source(self, camera_id: int, source: str) -> None:
        import cv2

        capture = None
        while not self._stop_event.is_set():
            capture = cv2.VideoCapture(source)
            if not capture.isOpened():
                logger.warning("Could not open RTSP source for camera %s", camera_id)
                capture.release()
                self._stop_event.wait(5)
                continue
            try:
                while not self._stop_event.is_set():
                    received, frame = capture.read()
                    if not received:
                        break
                    person_count = self._count_people(frame)
                    if person_count:
                        detection = PersonDetection(
                            camera_id=camera_id,
                            person_count=person_count,
                            detected_at=datetime.now(timezone.utc),
                        )
                        with self._lock:
                            self._detections[camera_id] = detection
                    self._stop_event.wait(settings.person_detection_frame_interval_seconds)
            except Exception:
                logger.exception("Person detection failed for camera %s", camera_id)
            finally:
                capture.release()
            self._stop_event.wait(2)

    def _load_model(self) -> None:
        from ultralytics import YOLO

        self._model = YOLO(settings.person_detection_model)

    def _count_people(self, frame: object) -> int:
        if self._model is None:
            return 0
        with self._model_lock:
            results = self._model(
                frame,
                classes=[0],
                conf=settings.person_detection_confidence,
                verbose=False,
            )
        return sum(len(result.boxes) for result in results)