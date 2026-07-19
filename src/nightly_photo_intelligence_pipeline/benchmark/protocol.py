"""Deterministic synthetic benchmark protocol for N2A."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class BenchmarkProfile(StrEnum):
    POSE = "pose"
    SEGMENTATION = "segmentation"


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    scenario: str
    fixture_ref: str
    image_width: int = 1920
    image_height: int = 1080
    expected_people: int = 1


@dataclass(frozen=True)
class BenchmarkPlan:
    profile: BenchmarkProfile
    cases: tuple[BenchmarkCase, ...]
    data_source: str = "synthetic_metadata_only"
    real_photo_reads: bool = False
    model_execution_authorized: bool = False

    @property
    def backend_candidates(self) -> tuple[str, ...]:
        return (f"fake-{self.profile.value}-v1",)

    @classmethod
    def for_profile(cls, profile: BenchmarkProfile) -> BenchmarkPlan:
        scenarios = (
            "single_person_full_body",
            "single_person_half_body",
            "seated_pose",
            "hand_near_face",
            "holding_object",
            "partial_occlusion",
            "two_people",
            "small_person",
            "cropped_subject",
            "collage_layout",
            "mirror_view",
            "left_right_ambiguity",
            "backlit_window",
            "hair_edge",
            "clothing_edge",
            "translucent_edge",
            "out_of_frame",
            "portrait_orientation",
            "landscape_orientation",
            "deterministic_rerun",
        )
        cases = tuple(
            BenchmarkCase(
                case_id=f"n2a-{profile.value}-{index:02d}",
                scenario=scenario,
                fixture_ref=f"synthetic_case_{index:02d}",
                expected_people=2 if scenario == "two_people" else 1,
            )
            for index, scenario in enumerate(scenarios, start=1)
        )
        return cls(profile=profile, cases=cases)

    def to_redacted_dict(self) -> dict[str, object]:
        return {
            "contract_type": "BENCHMARK_PLAN",
            "schema_version": "1.1",
            "profile": self.profile.value,
            "data_source": self.data_source,
            "real_photo_reads": self.real_photo_reads,
            "model_execution_authorized": self.model_execution_authorized,
            "case_count": len(self.cases),
            "required_metrics": [
                "processing_time",
                "gpu_peak_memory",
                "cpu_peak_memory",
                "deterministic_rerun",
                "schema_validation",
            ],
            "backend_candidates": list(self.backend_candidates),
            "measurement_status": "NOT_MEASURED",
            "cases": [
                {
                    "case_id": case.case_id,
                    "scenario": case.scenario,
                    "fixture_ref": case.fixture_ref,
                    "image_width": case.image_width,
                    "image_height": case.image_height,
                    "expected_people": case.expected_people,
                }
                for case in self.cases
            ],
        }
