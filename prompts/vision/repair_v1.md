---
id: repair_v1
strategy: repair
include_analysis: false
few_shot_examples: []
---
Your previous reply could not be used. Fix it so it is a single JSON object that follows the format below. Keep the same findings; change only what is needed to fix the format.

Problem found:
{{ERROR}}

Allowed strings:
part: {{PARTS}}
damage_type: {{DAMAGE_TYPES}}
severity: {{SEVERITIES}}
image_quality_flags entries look like "image_<index>_<issue>" with issue one of: {{QUALITY_ISSUES}}
image_index must be between 0 and {{MAX_IMAGE_INDEX}}.
If the previous reply describes no damage, use an empty damages array.

Required format:
{"damages": [{"part": "...", "damage_type": "...", "severity": "...", "confidence": 0.0, "image_index": 0, "notes": "..."}], "image_quality_flags": []}

Your previous reply:
<<<
{{PREVIOUS_REPLY}}
>>>

Return only the corrected JSON object.
