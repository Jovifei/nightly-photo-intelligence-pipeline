# Label Studio integration (offline exchange, not a new labeling platform)

Status: implemented JSON exchange + native Label Studio XML configuration;
server/UI round-trip and human review are NOT yet performed. Date: 2026-09-23.

The existing Real20 pipeline remains the producer. Label Studio provides the
human editing interface: images, facts/advice text, ACCEPT/EDIT/REJECT, issue
categories and revision notes. This repository does not reimplement that UI,
install a server, call its APIs or connect a cloud account.

## Reuse boundaries

- `review_config.xml` uses Label Studio's Image/Text/Choices/TextArea tag API.
- `real20/review_exchange.py` creates/reads its documented data/predictions/
  annotations JSON protocol. These are NPI-authored adapters, not copied upstream
  implementation code. Upstream Apache-2.0 licensing remains upstream.
- The adapter reuses existing `jsonschema` and `referencing` dependencies for a
  fixed, closed binding schema. Its registry explicitly refuses remote retrieval.
- Model predictions are immutable input, not human approval. Server-generated
  prediction IDs/timestamps are ignored, but prediction model_version/result and
  all task data must still match the preserved original tasks.
- Canceled annotations, missing tasks, duplicate active annotations, stale data,
  incorrect image/fact hashes and synthetic ACCEPT predictions cannot authorize
  a Bundle. An imported ACCEPT is recorded as a human choice; the result still
  says owner_approved=false and bundle_eligible=false.

## Local deployment (separate step, not executed by the pipeline)

Use a separately managed, locally reachable Label Studio instance. Do not put
its dependencies or database into the ML worker venv or share the Pipeline SQLite.
Do not expose it on LAN/internet or enable cloud storage/inference as a shortcut.
A server has its own storage; installing/starting it is not part of this code
handoff and must respect the Owner's local service/storage decisions.

Upstream latest-release API observed 1.23.0 on 2026-09-23. This is discovery,
not a security certification or a mandatory binary pin. Before installation,
recheck the chosen release and its official security advisories. No upstream
binary, model, dataset, license grant for photographs or server was downloaded.

Create a project using review_config.xml. Configure local file serving only for
an explicit external review-preview directory. Never set its document root to
the whole photo library or the drive root. Import an explicit task JSON file;
do not configure recursive discovery of the source library.

## Required external inputs after an authorized Real20 run

1. A COMPLETE Real20 result JSON and independently retained SHA-256.
2. An explicit preview map covering exactly the 19 canonical cases.
3. Already authorized, EXIF-free local previews under `real20-previews/`.
   This tool does NOT create previews or verify their pixels. The local reviewer
   must check that each image actually corresponds to its declared source SHA.
4. The original-photo root, used ONLY as a lexical exclusion for JSON I/O.
   The tool must not stat/traverse it to convert review artifacts.

Preview map shape (synthetic illustrative values only):

```json
{
  "real20-001": {
    "image_url": "/data/local-files/?d=real20-previews/real20-001.jpg",
    "source_sha256": "<exact SHA from authorized evaluation>"
  }
}
```

Use all 19 canonical entries. The one duplicate task reuses the canonical preview.
Network URLs, file://, traversal, arbitrary local paths and unmatched image SHAs
are rejected. No original filenames are added to the generated tasks.

## Executable workflow

With the existing supported interpreter and PYTHONPATH=src:

```text
python tools/real20_review_exchange.py export --help
python tools/real20_review_exchange.py import --help
```

Export requires --evaluation, --evaluation-sha256, --preview-map,
--source-root and --out. Save the output outside Git and the photo root. Existing
output is never overwritten. Preserve this exact original task file and its SHA.
Import that JSON in Label Studio; enable prediction display for the exact model
version. Do not configure the interface to preselect ACCEPT. A human must decide.

Export all tasks in full JSON (not JSON_MIN or CSV); include unannotated tasks
so missing decisions remain visible. Then import using --annotations,
--original-tasks, --original-tasks-sha256, --source-root and --out.

The CLI only exchanges JSON. The user's later Real20 execution authorization
must not be inferred merely because an adapter or XML file exists.

## Acceptance still required locally

- Actual Label Studio project accepts the XML and all 20 imported tasks.
- Preview 19+1 mapping is visually checked without giving server access to the
  unrestricted originals. No EXIF, location or identity metadata leaks.
- ACCEPT/EDIT/REJECT round-trip; missing/canceled/multiple annotations remain
  unresolved. Preserve original model data and actual reviewer IDs.
- Test metadata added by the chosen server version. A legitimate export rejected
  by the strict adapter is an interoperability gap to fix with a real fixture,
  not grounds to silently disable immutable-data checks.
- Owner approval/export to production Bundle remains a separate qualified step.

Official protocol sources:
https://labelstud.io/guide/tasks
https://labelstud.io/guide/predictions
https://labelstud.io/guide/export
https://labelstud.io/tags/choices
https://labelstud.io/tags/textarea
https://labelstud.io/guide/storage
