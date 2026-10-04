"""Spoken direction cues stay qualitative."""

from nightly_photo_intelligence_pipeline.direction.spoken import (
    qualitative_pose_cues,
    spoken_direction_request,
    validate_spoken,
)


def _point(x: float, y: float, score: float = 0.9) -> dict[str, float]:
    return {"x": x, "y": y, "score": score}


def test_cues_describe_limbs_without_scores() -> None:
    keypoints = [_point(0, 0, 0.0) for _ in range(17)]
    keypoints[0] = _point(100, 40)
    keypoints[5] = _point(80, 80)
    keypoints[6] = _point(120, 80)
    keypoints[7] = _point(70, 140)
    keypoints[8] = _point(150, 90)
    keypoints[9] = _point(70, 200)
    keypoints[10] = _point(170, 70)
    keypoints[11] = _point(90, 180)
    keypoints[12] = _point(120, 180)
    keypoints[13] = _point(90, 260)
    keypoints[14] = _point(130, 250)
    keypoints[15] = _point(90, 340)
    keypoints[16] = _point(140, 340)
    cues = qualitative_pose_cues(
        [{"box": {"x_min": 60, "y_min": 30, "x_max": 180, "y_max": 360}, "keypoints": keypoints}],
        400,
        400,
    )
    text = "\n".join(cues)
    assert "你的左臂" in text
    assert "你的右臂" in text
    assert "0.9" not in text
    assert "person_count" not in text


def test_empty_pose_does_not_invent_limbs() -> None:
    cues = qualitative_pose_cues([], 100, 100)
    assert "不要编造四肢" in cues[0]


def test_prompt_and_validator() -> None:
    prompt = spoken_direction_request(case_id="img-01-aaaaaaaa", pose_cues=["这个人。"])
    assert "构图" in prompt
    assert "img-01-aaaaaaaa" in prompt
    spoken = "站在画面中间，侧窗的光落在脸上。左臂微弯，右手自然下垂，眼睛看向镜头左侧，穿浅色衬衫。因为留白，这张照片才成立。" * 2
    assert validate_spoken(
        {"case_id": "img-01-aaaaaaaa", "spoken_direction": spoken, "simpler_alternative": "双手自然下垂，因为更好站稳。"},
        case_id="img-01-aaaaaaaa",
    ) is None
    assert validate_spoken(
        {"case_id": "img-01-aaaaaaaa", "spoken_direction": spoken + " pose_score 0.9", "simpler_alternative": "放下手。"},
        case_id="img-01-aaaaaaaa",
    )