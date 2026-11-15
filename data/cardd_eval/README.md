# Role 1 evaluation data

30 car photos with hand-drafted ground truth, used to compare prompt strategies.

| Split | Images | What is in it |
|---|---|---|
| `eval` | 20 | 15 damaged (CarDD), 2 damaged + synthetically degraded (blur, dark), 3 undamaged |
| `dev` | 10 | 8 damaged (CarDD), 1 damaged + degraded (low resolution), 1 undamaged |

Few-shot examples come only from `dev` (`dev_03` and `dev_10`). No `dev` image is ever scored, and no `eval` image is ever shown to the model as an example.

## Sources and licences

| Source | Used for | Licence | Link |
|---|---|---|---|
| CarDD (Wang, Li and Wu, IEEE T-ITS 2023), test split, via the Kaggle mirror "CarDD with YOLO Annotations" | 26 damaged images and their damage-type classes | CC BY-NC 4.0 on the mirror (non-commercial research use) | https://www.kaggle.com/datasets/gabrielfcarvalho/cardd-with-yolo-annotations-images-labels |
| CarDD COCO annotations for the same test split (used only to read the class list per image) | choosing images by damage type | CC0 as listed on Kaggle | https://www.kaggle.com/datasets/khanqanitah/cardd-test-set |
| Car Damage Assessment (Kaggle, "unknown" class) | 4 undamaged cars | CC0: Public Domain | https://www.kaggle.com/datasets/hamzamanssor/car-damage-assessment |

**Licence caveat to act on.** The official CarDD site (https://cardd-ustc.github.io/) gives the data only after a signed licence form is sent to the authors, for non-commercial research. The Kaggle mirror is a third-party re-upload. For an academic course project this is within the intended use, but the safe step before the final report is for the team to send the CarDD licence form and cite the paper:

> X. Wang, W. Li and Z. Wu, "CarDD: A New Dataset for Vision-Based Car Damage Detection," IEEE Transactions on Intelligent Transportation Systems, vol. 24, no. 7, pp. 7202-7214, 2023, doi: 10.1109/TITS.2023.3258480.

## How the 30 were picked

1. From the 374 CarDD test images, drew 7 random images per damage class (seed 42, at most 4 annotations each), giving 42 candidates.
2. Looked at each candidate with its CarDD boxes drawn on and dropped the ones where the damaged part could not be named (bare close-ups, a bus, door glass which has no part name in Contract A) and one near-duplicate pair (CarDD 001665 and 003283 show the same car; only 001665 is used).
3. Picked 4 clearly undamaged cars from the CC0 dataset (one has a bonnet decal, to test that decals are not reported as damage).
4. Made 3 bad-quality photos by degrading clear CarDD photos: Gaussian blur, darkening to 18 % brightness, and a 160 px down-scale with JPEG quality 10.

All images are resized to at most 1024 px on the long side (3.1 MB total), so they are committed. `scripts/build_dataset.py` rebuilds them from Kaggle.

## Labels (`labels.json`)

Each item uses the same field names and vocabularies as Contract A:

```json
{
  "image_id": "eval_05",
  "file": "images/eval_05.jpg",
  "split": "eval",
  "source": "cardd",
  "source_file": "000611.jpg",
  "category": "damaged",
  "degradation": null,
  "damages": [
    {"part": "left_taillamp", "damage_type": "lamp_broken", "severity": "severe"},
    {"part": "rear_bumper", "damage_type": "dent", "severity": "moderate"}
  ],
  "image_quality_flags": [],
  "cardd_classes": ["dent", "lamp_broken"],
  "side_uncertain": false,
  "labeled_by": "claude_draft",
  "verified_by_human": false,
  "label_notes": "..."
}
```

- `damage_type` follows the CarDD class for each damage region, except where the photo clearly shows more (eval_14: CarDD has no lamp label but the headlamp lens is gone, so `lamp_broken` was added) or where CarDD's class is a poor fit for the part (eval_02: the crumpled fender is labelled dent + scratch, CarDD says scratch). These are explained in `label_notes`.
- `part` and `severity` are **drafts made by Claude by looking at each photo**. CarDD has neither. They are marked `"labeled_by": "claude_draft"` and `"verified_by_human": false`. Aarti must check every one (see `docs/role1/REPORT.md` for the checklist) and flip `verified_by_human` to true.
- `side_uncertain: true` marks photos where the car's left/right or front/rear could not be read from the photo. The evaluation reports a corner-free part score so these do not decide the result.
- left/right always mean the car's own sides, as seen by a driver sitting inside facing forward.
- Severity follows `docs/role1/SEVERITY_RUBRIC.md`.

To rebuild the images: `python scripts/build_dataset.py --raw-dir ../vehicle-claim-genai-raw` (needs `~/.kaggle/kaggle.json`).
