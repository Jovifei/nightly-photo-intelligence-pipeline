"""Build a non-authorizing synthetic execution lease request packet.

This tool prepares Owner review material only. It never creates an APPROVED
execution lease or Owner trust anchor and never runs models, Ollama, photos,
EXIF, SQLite, App, or a production Bundle.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
REQUIRED_PATH_PLAN = {
    "inputs": {"old_s3", "old_s20", "s3_manifest", "s20_manifest", "baseline_manifest"},
    "outputs": {"s3_out", "s20_out", "evidence_out"},
    "protected": {
        "project_root",
        "ledger_root",
        "cache_root",
        "owner_anchor_root",
        "review_root",
        "lease_root",
        "quality_root",
        "prior_review_root",
    },
}


class RequestError(ValueError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise RequestError(code)


def canonical(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def strict_json(data: bytes) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            require(key not in result, "H0_DUPLICATE_JSON_MEMBER")
            result[key] = value
        return result

    def bad(_: str) -> None:
        raise RequestError("H0_NONFINITE_JSON")

    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=pairs, parse_constant=bad)
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise RequestError("H0_INVALID_JSON") from None


def run_git(root: Path, *args: str) -> bytes:
    env = {**os.environ, "GIT_NO_REPLACE_OBJECTS": "1", "GIT_OPTIONAL_LOCKS": "0"}
    for name in (
        "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    ):
        env.pop(name, None)
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), *args], capture_output=True, check=False, timeout=30, env=env
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RequestError("H0_GIT_UNAVAILABLE") from exc
    require(proc.returncode == 0, "H0_GIT_QUERY_FAILED")
    return proc.stdout


def source_identity(root: Path, expected_candidate: str) -> dict[str, Any]:
    require(HEX40.fullmatch(expected_candidate) is not None, "H0_EXPECTED_CANDIDATE_INVALID")
    head = run_git(root, "rev-parse", "HEAD").decode().strip()
    tree = run_git(root, "rev-parse", "HEAD^{tree}").decode().strip()
    require(head == expected_candidate, "H0_CANDIDATE_MISMATCH")
    require(HEX40.fullmatch(tree) is not None, "H0_TREE_INVALID")
    require(run_git(root, "status", "--porcelain=v1", "--untracked-files=all") == b"", "H0_WORKTREE_DIRTY")
    require(run_git(root, "rev-parse", "--is-shallow-repository").strip() == b"false", "H0_SHALLOW_REPOSITORY")
    rows: list[dict[str, Any]] = []
    total = 0
    for entry in run_git(root, "ls-tree", "-rz", "--full-tree", "HEAD").split(b"\0"):
        if not entry:
            continue
        try:
            meta, raw_path = entry.split(b"\t", 1)
            mode, kind, oid = meta.decode("ascii").split()
            path = raw_path.decode("utf-8")
        except (ValueError, UnicodeError):
            raise RequestError("H0_GIT_TREE_INVALID") from None
        require(kind == "blob" and mode in {"100644", "100755"}, "H0_UNSUPPORTED_GIT_ENTRY")
        require(not path.startswith("/") and ".." not in path.split("/") and "\n" not in path and "\r" not in path,
                "H0_GIT_PATH_INVALID")
        size = int(run_git(root, "cat-file", "-s", oid))
        require(0 <= size <= 8 * 1024 * 1024, "H0_SOURCE_BLOB_SIZE_LIMIT")
        total += size
        require(total <= 128 * 1024 * 1024 and len(rows) < 5000, "H0_SOURCE_SIZE_LIMIT")
        data = run_git(root, "cat-file", "blob", oid)
        require(len(data) == size, "H0_SOURCE_BLOB_CHANGED")
        rows.append({"path": path, "mode": mode, "git_blob": oid, "size_bytes": size, "sha256": sha(data)})
    require(bool(rows), "H0_EMPTY_SOURCE_TREE")
    rows.sort(key=lambda item: item["path"])
    require(run_git(root, "rev-parse", "HEAD").decode().strip() == head, "H0_SOURCE_CHANGED")
    return {
        "candidate_commit": head,
        "candidate_tree": tree,
        "source_manifest_sha256": sha(canonical(rows)),
        "file_count": len(rows),
    }


def digest_file(path: Path, code: str) -> str:
    try:
        info = path.lstat()
        data = path.read_bytes()
    except OSError as exc:
        raise RequestError(code) from exc
    require(path.is_file() and not path.is_symlink() and info.st_nlink == 1, code)
    return sha(data)


def load_runtime_identity(path: Path) -> tuple[dict[str, Any], str]:
    try:
        payload = strict_json(path.read_bytes())
    except OSError as exc:
        raise RequestError(H0_RUNTIME_IDENTITY_MISSING) from exc
    required = {
        "model_name", "full_local_digest", "size_bytes", "quantization_level", "capabilities", "ollama_version"
    }
    require(isinstance(payload, dict) and set(payload) == required, "H0_RUNTIME_IDENTITY_INVALID")
    require(payload["model_name"] == "qwen3.5:9b", "H0_RUNTIME_IDENTITY_INVALID")
    require(isinstance(payload["full_local_digest"], str) and HEX64.fullmatch(payload["full_local_digest"]),
            "H0_RUNTIME_IDENTITY_INVALID")
    require(type(payload["size_bytes"]) is int and payload["size_bytes"] > 0, "H0_RUNTIME_IDENTITY_INVALID")
    require(payload["quantization_level"] == "Q4_K_M", "H0_RUNTIME_IDENTITY_INVALID")
    caps = payload["capabilities"]
    require(isinstance(caps, list) and all(isinstance(x, str) and x for x in caps) and "vision" in caps,
            "H0_RUNTIME_IDENTITY_INVALID")
    require(isinstance(payload["ollama_version"], str) and payload["ollama_version"], "H0_RUNTIME_IDENTITY_INVALID")
    normalized = {'–ÆöBÂ&6&–Æ—F–W2#¢6÷'FVB‡6WB†62’—Ð¢&WGW&âæ÷&ÖÆ—¦VBÂ6††6æöæ–6Â†æ÷&ÖÆ—¦VB’  ¦FVbÆöE÷F…÷Æâ‡Fƒ¢F‚’ÓâGWÆU¶F–7E·7G"ÂF–7E·7G"Â7G%ÕÒÂ7G%Ó ¢G'“ ¢–ÆöBÒ7G&–7Eö§6öâ‡F‚ç&VEö'—FW2‚’¢W†6WBõ4W'&÷"2W†3 ¢&—6R&WVW7DW'&÷"„ƒõD…õÄåôÔ•54”är’g&öÒW†0¢&WV—&R†—6–ç7Fæ6R‡–ÆöBÂF–7B’æB6WB‡–ÆöB’ÓÒ6WB…$UT•$TEõD…õÄâ’Â$ƒõD…õÄåô”ådÄ”B"¢&W7VÇC¢F–7E·7G"ÂF–7E·7G"Â7G%ÕÒÒ·Ð¢ÆÅ÷F‡3¢Æ—7E·7G%ÒÒµÐ¢f÷"6V7F–öâÂÆ&VÇ2–â$UT•$TEõD…õÄâæ—FV×2‚“ ¢fÇVRÒ–ÆöE·6V7F–öåÐ¢&WV—&R†—6–ç7Fæ6R‡fÇVRÂF–7B’æB6WB‡fÇVR’ÓÒÆ&VÇ2Â$ƒõD…õÄåô”ådÄ”B"¢6V7F–öåö÷WC¢F–7E·7G"Â7G%ÒÒ·Ð¢f÷"Æ&VÂ–â6÷'FVB†Æ&VÇ2“ ¢&rÒfÇVU¶Æ&VÅÐ¢&WV—&R†—6–ç7Fæ6R‡&rÂ7G"’æB&ræB"ââ"æ÷B–âF‚‡&r’ç'G2Â$ƒõD…õÄåô”ådÄ”B"¢&WV—&R†æ÷B&rç7F'G7v—F‚‚‚%ÅÅÅÂ"Â"òò"’’Â$ƒõD…õÄåô”ådÄ”B"¢6V7F–öåö÷WE¶Æ&VÅÒÒ&p¢ÆÅ÷F‡2æVæB†÷2çF‚ææ÷&Ö66R†÷2çF‚æ'7F‚‡&r’’¢&W7VÇE·6V7F–öåÒÒ6V7F–öåö÷W@¢&WV—&R†ÆVâ‡6WB†ÆÅ÷F‡2’’ÓÒÆVâ†ÆÅ÷F‡2’Â$ƒõD…õÄåô4ôÄÄ•4”ôâ"¢&WGW&â&W7VÇBÂ6††6æöæ–6Â‡&W7VÇB’  ¦FVb&ö¦V7E÷7FFR‡&ö÷C¢F‚’ÓâGWÆU·7G"ÂF–7E·7G"Âç•ÕÓ ¢F‚Ò&ö÷Bò%$ô¤T5Eõ5DDRæ§6öâ ¢G'“ ¢FFÒF‚ç&VEö'—FW2‚¢W†6WBõ4W'&÷"2W†3 ¢&—6R&WVW7DW'&÷"‚$ƒõ$ô¤T5Eõ5DDUôÔ•54”är"’g&öÒW†0¢–ÆöBÒ7G&–7Eö§6öâ†FF¢&WV—&R†—6–ç7Fæ6R‡–ÆöBÂF–7B’Â$ƒõ$ô¤T5Eõ5DDUô”ådÄ”B"¢†6W2Ò–ÆöBævWB‚'†6U÷7FGW2"¢&WV—&R†—6–ç7Fæ6R‡†6W2ÂF–7B’æB†6W2ævWB‚$ã$#""’ÓÒ$Äô4´TB"Â$ƒôã$#%ôäõEôÄô4´TB"¢&WGW&â6††FF’Â–Æö@  ¦FVb'V–ÆE÷&WVW7B†&w3¢&w'6RäæÖW76R’ÓâF–7E·7G"Âç•Ó ¢6÷W&6RÒ6÷W&6Uö–FVçF—G’†&w2æ6æF–FFU÷&ö÷BÂ&w2æW‡V7FVEö6æF–FFR¢7FFU÷6†ÂòÒ&ö¦V7E÷7FFR†&w2æ6æF–FFU÷&ö÷B¢–FVçF—G’Â–FVçF—G•÷6†ÒÆöE÷'VçF–ÖUö–FVçF—G’†&w2ç'VçF–ÖUö–FVçF—G’¢F…÷ÆâÂF…÷6†ÒÆöE÷F…÷Æâ†&w2çF…÷Æâ¢66†RÒ&w2æÖöFVÅö66†Uö&–æF–æu÷6†#S`¢&WV—&R„„UƒcBægVÆÆÖF6‚†66†R’—2æ÷BæöæRÂ$ƒô44„Uô$”äD”äuô”ådÄ”B"¢35÷6†ÒF–vW7Eöf–ÆR†&w2ç35öÖæ–fW7BÂ$ƒõ35ôÔä”dU5Eô”ådÄ”B"¢3#÷6†ÒF–vW7Eöf–ÆR†&w2ç3#öÖæ–fW7BÂ$ƒõ3#ôÔä”dU5Eô”ådÄ”B"¢&Wf–Wu÷6†ÒF–vW7Eöf–ÆR†&w2ç&Wf–Wuö'F–f7BÂ$ƒõ$Ud”Uuô%D”d5Eô”ådÄ”B"¢VÆ—G•÷6†ÒF–vW7Eöf–ÆR†&w2çVÆ—G•öWf–FVæ6RÂ$ƒõTÄ•E•ôUd”DTä4Uô”ådÄ”B"¢&÷÷6VBÒ°¢'66†VÖ÷fW'6–öâ#¢&ç’×7–çF†WF–2ÖW†V7WF–öâÖÆV6R×c""À¢'7FGW2#¢$E$eB"À¢&÷væW%ö–B#¢$¦÷f’"À¢'W'÷6R#¢%5”åD„UD”5õ35õ3#ôTät”äTU$”äuõdÄ”DD”ôâ"À¢&æ÷Eö&Vf÷&U÷WF2#¢æöæRÀ¢&W‡—&W5öE÷WF2#¢æöæRÀ¢&&–æF–æw2#¢°¢&6æF–FFUö6öÖÖ—B#¢6÷W&6U²&6æF–FFUö6öÖÖ—B%ÒÀ¢&6æF–FFU÷G&VR#¢6÷W&6U²&6æF–FFU÷G&VR%ÒÀ¢'6÷W&6UöÖæ–fW7E÷6†#Sb#¢6÷W&6U²'6÷W&6UöÖæ–fW7E÷6†#Sb%ÒÀ¢'&ö¦V7E÷7FFU÷6†#Sb#¢7FFU÷6†À¢''VçF–ÖUö–FVçF—G•÷6†#Sb#¢–FVçF—G•÷6†À¢'35öÖæ–fW7E÷6†#Sb#¢35÷6†À¢'3#öÖæ–fW7E÷6†#Sb#¢3#÷6†À¢&ÖöFVÅö66†Uö&–æF–æu÷6†#Sb#¢66†RÀ¢'F…÷Æå÷6†#Sb#¢F…÷6†À¢ÒÀ¢&&÷VæF&–W2#¢°¢'&VÅ÷†÷Fò#¢fÇ6RÂ'&VÅöW†–b#¢fÇ6RÂ&s÷6÷W&6R#¢fÇ6RÂ'7Æ—FUö–ævW7B#¢fÇ6RÀ¢&#¢fÇ6RÂ'&öGV7F–öåö'VæFÆR#¢fÇ6RÂ&ÖöFVÅöF÷væÆöB#¢fÇ6RÀ¢&ÖöFVÅ÷&WÆ6VÖVçB#¢fÇ6RÂ'&ö¦V7E÷7FFUö×WFF–öâ#¢fÇ6RÀ¢ÒÀ¢&Ö…ög&W6…÷35÷'Vç2#¢À¢&Ö…ög&W6…÷3#÷'Vç2#¢À¢'&öGV7F–öå÷VæÆö6²#¢fÇ6RÀ¢Ð¢&WGW&â°¢'66†VÖ÷fW'6–öâ#¢&ç’×7–çF†WF–2ÖÆV6R×&WVW7B×c"À¢'7FGW2#¢$E$eEôõtäU%õ$Ud”Uuõ$UT•$TB"À¢&W†V7WF–öåöWF†÷&—¦VB#¢fÇ6RÀ¢&÷væW%öæ6†÷%ö7&VFVB#¢fÇ6RÀ¢&6æF–FFR#¢6÷W&6RÀ¢'&ö¦V7E÷7FFU÷6†#Sb#¢7FFU÷6†À¢'&Wf–Wuö'F–f7E÷6†#Sb#¢&Wf–Wu÷6†À¢'VÆ—G•öWf–FVæ6U÷6†#Sb#¢VÆ—G•÷6†À¢''VçF–ÖUö–FVçF—G’#¢–FVçF—G’À¢''VçF–ÖUö–FVçF—G•÷6†#Sb#¢–FVçF—G•÷6†À¢'F…÷Æâ#¢F…÷ÆâÀ¢'F…÷Æå÷6†#Sb#¢F…÷6†À¢'&÷÷6VEöÆV6R#¢&÷÷6VBÀ¢'&WV—&VEö÷væW%ö7F–öç2#¢°¢&–æFWVæFVçFÇ’fW&–g’F†—2&WVW7B6¶WBæBÆÂW‡FW&æÂWf–FVæ6R"À¢&6†ö÷6RâW‡Æ–6—Bæ÷Eö&Vf÷&U÷WF2æBW‡—&W5öE÷WF2"À¢&6†ævR7FGW2Fò$õdTBöæÇ’–ââ÷væW"Ö6öçG&öÆÆVBv—BÖW‡FW&æÂÆV6RgFW"&÷fÂ"À¢&7&VFRF†R6W&FR÷væW"æ6†÷"öæÇ’gFW"†6†–ærF†RW†7B&÷fVBÆV6R'—FW2"À¢&Fòæ÷BWF†÷&—¦R&VÃ#÷"&öGV7F–öâã$#"F‡&÷Vv‚F†—27–çF†WF–2ÆV6R"À¢ÒÀ¢Ð  ¦FVbÖ–â‚’Óâ–çC ¢'6W"Ò&w'6Rä&wVÖVçE'6W"†FW67&—F–öãÕõöFö5õò¢'6W"æFEö&wVÖVçB‚"ÒÖ6æF–FFR×&ö÷B"ÂG—SÕF‚Â&WV—&VCÕG'VR¢'6W"æFEö&wVÖVçB‚"ÒÖW‡V7FVBÖ6æF–FFR"Â&WV—&VCÕG'VR¢'6W"æFEö&wVÖVçB‚"Ò×&Wf–WrÖ'F–f7B"ÂG—SÕF‚Â&WV—&VCÕG'VR¢'6W"æFEö&wVÖVçB‚"Ò×VÆ—G’ÖWf–FVæ6R"ÂG—SÕF‚Â&WV—&VCÕG'VR¢'6W"æFEö&wVÖVçB‚"Ò×'VçF–ÖRÖ–FVçF—G’"ÂG—SÕF‚Â&WV—&VCÕG'VR¢'6W"æFEö&wVÖVçB‚"Ò×32ÖÖæ–fW7B"ÂG—SÕF‚Â&WV—&VCÕG'VR¢'6W"æFEö&wVÖVçB‚"Ò×3#ÖÖæ–fW7B"ÂG—SÕF‚Â&WV—&VCÕG'VR¢'6W"æFEö&wVÖVçB‚"ÒÖÖöFVÂÖ66†RÖ&–æF–ær×6†#Sb"Â&WV—&VCÕG'VR¢'6W"æFEö&wVÖVçB‚"Ò×F‚×Æâ"ÂG—SÕF‚Â&WV—&VCÕG'VR¢'6W"æFEö&wVÖVçB‚"ÒÖ÷WB"ÂG—SÕF‚Â&WV—&VCÕG'VR¢&w2Ò'6W"ç'6Uö&w2‚¢G'“ ¢6¶WBÒ'V–ÆE÷&WVW7B†&w2¢&WV—&R†æ÷B&w2æ÷WBæW†—7G2‚’Â$ƒôõUEUEôÅ$TE•ôU„•5E2"¢&w2æ÷WBç&VçBæÖ¶F—"‡&VçG3ÕG'VRÂW†—7Eöö³ÕG'VR¢&w2æ÷WBçw&—FUö'—FW2†6æöæ–6Â‡6¶WB’¢W†6WB&WVW7DW'&÷"2W†3 ¢&–çB‡7G"†W†2’¢&WGW&â¢W†6WB„õ4W'&÷"ÂfÇVTW'&÷"’2W†3 ¢&–çB‚$ƒõ$UTU5Eô%T”ÄEôd”ÄTB"ÂG—R†W†2’åõöæÖUõò¢&WGW&â¢&–çB‚$ƒôE$eEõ$UTU5Eô5$TDTEôäõEôUD„õ$•¤TB"¢&–çB‚'&WVW7E÷6†#Sb"Â6††&w2æ÷WBç&VEö'—FW2‚’’¢&WGW&â   ¦–bõöæÖUõòÓÒ%õöÖ–åõò# ¢&—6R7—7FVÔW†—B†Ö–â‚’ 