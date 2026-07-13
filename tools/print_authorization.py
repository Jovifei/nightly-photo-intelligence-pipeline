#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
state = json.loads((root / "PROJECT_STATE.json").read_text(encoding="utf-8"))
auth = state["authorization"]

print("Project:", state["project"]["slug"])
print("Phase:", auth["phase"]["id"], auth["phase"]["status"])
print("Data gate:", auth["data_gate"]["id"], auth["data_gate"]["status"])
print("Real photo access:", auth["real_photo_access"])
print("Model downloads:", auth["large_model_downloads"])
print("OpenClaw:", auth["openclaw_activation"])
print("Locked phases:", ", ".join(state["locked"]["phases"]))
print("Required stop:", state["required_stop_after"]["next_action"])
