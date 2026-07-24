# N2B0.5 upstream rights questions (draft, not sent)

No external issue, email, or comment was sent. These questions are for Owner
review and legal clarification only.

## MMPose / OpenMMLab

1. For each named `.pth` URL, what exact weight/checkpoint license governs the
   binary, and is commercial use and redistribution permitted?
2. Is the filename/date/checksum suffix an immutable release identifier? If
   not, please publish a versioned artifact record and SHA-256.
3. Are COCO-WholeBody and any auxiliary training data subject to additional
   restrictions relevant to commercial inference or redistribution?
4. Is there a NOTICE/attribution obligation for the checkpoint distinct from
   the Apache-2.0 code repository?

## PaddleSeg / PP-HumanSegV2-Lite

1. Does the Apache-2.0 repository license apply to the exact 192x192 inference
   ZIP, or is a separate weight/model license supplied?
2. Does “zero cost” include commercial redistribution and use, and are there
   dataset, patent, or attribution conditions?
3. Please publish an immutable artifact revision and SHA-256 for the exact ZIP.

## MediaPipe Selfie Segmentation

1. What weight/model license and commercial-use terms govern each linked TFLite
   file, separate from the MediaPipe Apache-2.0 source license?
2. Is there an immutable revision or signed checksum for the two storage
   objects, and what NOTICE/attribution is required?
3. Are the legacy solution/model-card terms still the authoritative terms for
   these objects, or has a replacement model superseded them?
