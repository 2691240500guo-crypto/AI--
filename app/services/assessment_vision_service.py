"""答题过程中的轻量视觉防作弊分析。

YOLO 负责目标检测（人、手机等），MediaPipe 负责面部关键点。
模型按需加载，依赖或权重缺失时自动降级，不影响测评主流程。
"""

from __future__ import annotations

import base64
import time
from functools import lru_cache
from typing import Any

from app.core.config import get_settings


@lru_cache(maxsize=1)
def _load_models() -> tuple[Any, Any, str | None]:
    """按需加载 YOLO（必需）和 MediaPipe（可选）。

    MediaPipe 在 ≥0.10 移除了 `solutions` 子模块，老代码访问会抛 AttributeError。
    加载失败时降级为仅 YOLO，多人/违规物品检测仍可用，丢失的仅是「未检测到人脸」信号。
    """
    settings = get_settings()
    if not settings.ANTI_CHEAT_ENABLED:
        return None, None, "disabled"
    import logging
    logger = logging.getLogger(__name__)
    # —— YOLO（必需，加载失败 = 整体不可用）——
    try:
        from ultralytics import YOLO
        detector = YOLO(settings.ANTI_CHEAT_MODEL_PATH)
    except Exception as exc:
        logger.warning("YOLO 加载失败: %s: %s", type(exc).__name__, exc)
        return None, None, f"YOLO 加载失败: {type(exc).__name__}: {exc}"
    # —— MediaPipe（可选，加载失败仅记录警告，降级运行）——
    face_mesh = None
    try:
        import mediapipe as mp
        face_mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=3,
            refine_landmarks=True,
            min_detection_confidence=0.5,
        )
    except Exception as exc:
        logger.warning("MediaPipe 加载失败（仅用 YOLO 降级）: %s: %s", type(exc).__name__, exc)
    return detector, face_mesh, None


class AssessmentVisionService:
    @staticmethod
    def analyze_frame(frame_base64: str) -> dict[str, Any]:
        settings = get_settings()
        if not settings.ANTI_CHEAT_ENABLED:
            return {"status": "disabled", "signals": [], "message": "视觉防作弊未启用"}
        if not frame_base64:
            raise ValueError("缺少摄像头帧")
        encoded = frame_base64.split(",", 1)[1] if "," in frame_base64 else frame_base64
        try:
            raw = base64.b64decode(encoded, validate=True)
        except Exception as exc:
            raise ValueError("摄像头帧不是有效的 Base64 图片") from exc
        if len(raw) > settings.ANTI_CHEAT_MAX_FRAME_BYTES:
            raise ValueError("摄像头帧过大")

        detector, face_mesh, load_error = _load_models()
        if detector is None:
            return {"status": "unavailable", "signals": [], "message": "视觉模型暂不可用", "detail": load_error}

        import cv2
        import numpy as np

        image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("无法解析摄像头图片")
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        # MediaPipe 可选：仅在加载成功时跑人脸检测；不可用时 face_count=0，避免误报 no_face
        face_count = 0
        face_detection_available = False
        if face_mesh is not None:
            try:
                result = face_mesh.process(rgb)
                face_count = len(result.multi_face_landmarks or [])
                face_detection_available = True
            except Exception as exc:
                import logging
                logging.getLogger(__name__).warning("MediaPipe 推理失败: %s: %s", type(exc).__name__, exc)
        detections = detector.predict(image, conf=settings.ANTI_CHEAT_CONFIDENCE, verbose=False)[0]
        names = detections.names or {}
        objects: list[dict[str, Any]] = []
        for box in detections.boxes:
            cls_id = int(box.cls[0])
            label = str(names.get(cls_id, cls_id))
            if label in {"person", "cell phone", "laptop", "tablet"}:
                objects.append({"label": label, "confidence": round(float(box.conf[0]), 3)})

        person_count = sum(1 for item in objects if item["label"] == "person")
        signals: list[str] = []
        # 多人判定直接用 YOLO 人数（不依赖 MediaPipe），即使人脸检测降级也能触发
        if person_count > 1:
            signals.append("multiple_people")
        # no_face 仅在人脸检测可用时判定：单人同框但 0 张脸 = 低头/背对/离席
        if face_detection_available and face_count == 0:
            signals.append("no_face")
        if any(item["label"] in {"cell phone", "laptop", "tablet"} for item in objects):
            signals.append("unauthorized_device")
        return {
            "status": "ok",
            "signals": signals,
            "face_count": face_count,
            "person_count": person_count,
            "objects": objects,
            "face_detection_available": face_detection_available,
            "analyzed_at": int(time.time()),
        }
