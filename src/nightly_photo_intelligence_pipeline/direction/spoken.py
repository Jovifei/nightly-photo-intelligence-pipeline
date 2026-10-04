"""Turn a reference photo into photographer-spoken direction.

Builds on prompts/director_prompts_v1.prompt.md: the product is speech a
photographer can say so a model can copy the pose. Head counts, pose scores,
and mask ratios are not part of this text. Pose keypoints are only an internal
cue for how the limbs bend.
"""

from __future__ import annotations

import math
from typing import Any

# COCO person keypoints. "left"/"right" are the subject's, not the image's.
_NOSE = 0
_LEFT_EAR = 3
_RIGHT_EAR = 4
_LEFT_SHOULDER = 5
_RIGHT_SHOULDER = 6
_LEFT_ELBOW = 7
_RIGHT_ELBOW = 8
_LEFT_WRIST = 9
_RIGHT_WRIST = 10
_LEFT_HIP = 11
_RIGHT_HIP = 12
_LEFT_KNEE = 13
_RIGHT_KNEE = 14
_LEFT_ANKLE = 15
_RIGHT_ANKLE = 16

_VISIBLE = 0.35

SPOKEN_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["case_id", "spoken_direction", "simpler_alternative"],
    "properties": {
        "case_id": {"type": "string"},
        "spoken_direction": {"type": "string"},
        "simpler_alternative": {"type": "string"},
    },
}


def _pt(keypoints: list[dict[str, float]], index: int) -> dict[str, float] | None:
    if index >= len(keypoints):
        return None
    point = keypoints[index]
    try:
        score = float(point.get("score", 0.0))
        x = float(point["x"])
        y = float(point["y"])
    except (TypeError, ValueError, KeyError):
        return None
    if score < _VISIBLE or not math.isfinite(x) or not math.isfinite(y):
        return None
    return {"x": x, "y": y}


def _angle_deg(a: dict[str, float], b: dict[str, float], c: dict[str, float]) -> float | None:
    ax, ay = a["x"] - b["x"], a["y"] - b["y"]
    cx, cy = c["x"] - b["x"], c["y"] - b["y"]
    na, nc = math.hypot(ax, ay), math.hypot(cx, cy)
    if na == 0.0 or nc == 0.0:
        return None
    cosine = max(-1.0, min(1.0, (ax * cx + ay * cy) / (na * nc)))
    return math.degrees(math.acos(cosine))


def _bend(angle: float | None) -> str:
    if angle is None:
        return "弯曲程度看不清"
    if angle >= 150:
        return "几乎伸直"
    if angle >= 100:
        return "微弯"
    if angle >= 60:
        return "明显弯曲"
    return "折得很紧"


def _arm(side: str, shoulder: dict[str, float] | None, elbow: dict[str, float] | None, wrist: dict[str, float] | None) -> str:
    if shoulder is None or elbow is None:
        return f"你的{side}臂看不清，不要猜"
    bend = _bend(_angle_deg(shoulder, elbow, wrist) if wrist else None)
    if wrist is None:
        return f"你的{side}臂{bend}，手的位置看不清"
    if wrist["y"] < shoulder["y"] - 15:
        height = "手抬到肩以上"
    elif wrist["y"] < elbow["y"]:
        height = "手在肘和肩之间"
    else:
        height = "手在肘以下"
    across = ""
    if side == "左" and wrist["x"] > shoulder["x"] + 20:
        across = "，手收到身前或身体另一侧"
    if side == "右" and wrist["x"] < shoulder["x"] - 20:
        across = "，手收到身前或身体另一侧"
    return f"你的{side}臂{bend}，{height}{across}"


def _leg(side: str, hip: dict[str, float] | None, knee: dict[str, float] | None, ankle: dict[str, float] | None) -> str:
    if hip is None or knee is None:
        return f"你的{side}腿看不清，不要猜"
    bend = _bend(_angle_deg(hip, knee, ankle) if ankle else None)
    if ankle is None:
        return f"你的{side}腿{bend}，脚出画或看不清"
    if knee["y"] < hip["y"] + 25:
        posture = "大腿抬起或盘着"
    elif ankle["y"] < knee["y"] + 20:
        posture = "小腿折起"
    else:
        posture = "小腿向下"
    return f"你的{side}腿{bend}，{posture}"


def _head(keypoints: list[dict[str, float]]) -> str:
    nose = _pt(keypoints, _NOSE)
    left_ear = _pt(keypoints, _LEFT_EAR)
    right_ear = _pt(keypoints, _RIGHT_EAR)
    left_shoulder = _pt(keypoints, _LEFT_SHOULDER)
    right_shoulder = _pt(keypoints, _RIGHT_SHOULDER)
    if nose is None or left_shoulder is None or right_shoulder is None:
        return "头的朝向看不清，以照片里的脸为准"
    mid_x = (left_shoulder["x"] + right_shoulder["x"]) / 2.0
    span = max(abs(left_shoulder["x"] - right_shoulder["x"]), 1.0)
    shift = (nose["x"] - mid_x) / span
    if abs(shift) < 0.18:
        facing = "鼻子大致在两肩中间，脸多半朝前"
    elif shift < 0:
        facing = "鼻子偏到画面左侧，头转向画面左侧"
    else:
        facing = "鼻子偏到画面右侧，头转向画面右侧"
    ears = ""
    if left_ear is not None and right_ear is None:
        ears = "；你的左耳更清楚，脸有一点侧过去"
    elif right_ear is not None and left_ear is None:
        ears = "；你的右耳更清楚，脸有一点侧过去"
    return facing + ears + "。眼睛看哪里要直接看照片，不要用关键点猜目光"


def _frame(box: dict[str, float] | None, width: int, height: int) -> str:
    if not box or width <= 0 or height <= 0:
        return "人在画面中的位置不确定"
    cx = (float(box["x_min"]) + float(box["x_max"])) / 2.0 / width
    cy = (float(box["y_min"]) + float(box["y_max"])) / 2.0 / height
    if cx < 0.38:
        horizontal = "人在画面左侧"
    elif cx > 0.62:
        horizontal = "人在画面右侧"
    else:
        horizontal = "人在画面中间"
    if cy < 0.38:
        vertical = "偏上"
    elif cy > 0.62:
        vertical = "偏下"
    else:
        vertical = "上下居中"
    edges: list[str] = []
    if float(box["y_min"]) <= 1:
        edges.append("头顶贴边或出画")
    if float(box["y_max"]) >= height - 1:
        edges.append("脚下贴边或出画")
    if float(box["x_min"]) <= 1:
        edges.append("画面左侧贴边")
    if float(box["x_max"]) >= width - 1:
        edges.append("画面右侧贴边")
    crop = ("，" + "、".join(edges)) if edges else "，人没有贴死四边"
    return f"{horizontal}，{vertical}{crop}"


def _slot_label(index: int, total: int) -> str:
    if total <= 1:
        return "这个人"
    if index == 0:
        return "画面最左边的人"
    if index == total - 1:
        return "画面最右边的人"
    if index < total / 2:
        return "画面中间、更靠左的人"
    return "画面中间、更靠右的人"


def qualitative_pose_cues(
    people: list[dict[str, Any]],
    width: int,
    height: int,
) -> list[str]:
    """Chinese limb cues. No scores, no head count, no mask ratio."""

    if not people:
        return ["没有可靠的人体关键点。只根据照片讲构图和光线，不要编造四肢。"]
    ordered = sorted(
        people,
        key=lambda person: float((person.get("box") or {}).get("x_min", 0.0)),
    )
    cues: list[str] = []
    total = len(ordered)
    for index, person in enumerate(ordered):
        keypoints = list(person.get("keypoints") or [])
        parts = [
            _slot_label(index, total),
            _frame(person.get("box"), width, height),
            _head(keypoints),
            _arm("左", _pt(keypoints, _LEFT_SHOULDER), _pt(keypoints, _LEFT_ELBOW), _pt(keypoints, _LEFT_WRIST)),
            _arm("右", _pt(keypoints, _RIGHT_SHOULDER), _pt(keypoints, _RIGHT_ELBOW), _pt(keypoints, _RIGHT_WRIST)),
            _leg("左", _pt(keypoints, _LEFT_HIP), _pt(keypoints, _LEFT_KNEE), _pt(keypoints, _LEFT_ANKLE)),
            _leg("右", _pt(keypoints, _RIGHT_HIP), _pt(keypoints, _RIGHT_KNEE), _pt(keypoints, _RIGHT_ANKLE)),
        ]
        cues.append("。".join(parts) + "。")
    return cues


def spoken_direction_request(*, case_id: str, pose_cues: list[str]) -> str:
    """Prompt for one spoken direction. Echoes director-prompt channels as speech."""

    cues = "\n".join(f"- {cue}" for cue in pose_cues)
    return (
        "你是现场摄影师，正在对着模特说话。下面给你一张参考照片，请说出一段可以照着做的口播。\n"
        "这段话就是产品。用简体中文，像口头指导，不要写成报表。\n"
        "必须讲清这六件事：构图和画面布局；光从哪里来、落在哪里；身体姿态以及四肢怎样配合；"
        "眼睛看向哪里；服装风格；这张照片为什么成立。\n"
        "姿态以照片为准。下面的关键点观察只用来核对手臂和腿是弯还是直，不要复述分数，不要说有几个人，"
        "不要说遮罩占比，不要报文件名或真实姓名。\n"
        "沿用既有导演提示的口吻：主动作用短句，让人做得到；如果原姿势太难，simpler_alternative "
        "用一句更简单的做法，并说明为什么更简单。不要给精确焦段、真实安全距离或原调色参数。\n"
        "不要色情化。如果画面里的人看起来是未成年人，只做非性的构图、光线、端正姿态和服装风格指导，"
        "不要评论身体、吸引力或脆弱感。\n"
        f"case_id={case_id}。spoken_direction 和 simpler_alternative 都必须回写这个 case_id。\n"
        "关键点观察（内部，不是给客户看的原文）：\n"
        f"{cues}\n"
    )


def validate_spoken(payload: dict[str, Any], *, case_id: str) -> str | None:
    """Return an error string, or None when the payload is usable product text."""

    if not isinstance(payload, dict):
        return "response is not an object"
    if payload.get("case_id") != case_id:
        return "case_id mismatch"
    spoken = payload.get("spoken_direction")
    simpler = payload.get("simpler_alternative")
    if not isinstance(spoken, str) or not isinstance(simpler, str):
        return "missing text fields"
    cjk = sum(1 for ch in spoken if "\u4e00" <= ch <= "\u9fff")
    if cjk < 40 or len(spoken.strip()) < 80:
        return "spoken_direction too short or not Chinese"
    if len(simpler.strip()) < 8:
        return "simpler_alternative empty"
    banned = ("person_count", "pose_score", "pose_confidence", "segmentation", "关键点分数")
    blob = spoken + simpler
    for word in banned:
        if word in blob:
            return f"product text contains internal field {word}"
    if "光" not in spoken:
        return "spoken_direction does not say where the light is"
    if not any(word in spoken for word in ("成立", "因为", "所以", "之所以")):
        return "spoken_direction does not say why the photo works"
    return None