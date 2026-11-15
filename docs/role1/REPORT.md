# Role 1 report sections

## Literature survey

This survey should be completed with peer-reviewed sources before submission. The project compares visual damage assessment using a vision-language model (VLM), but this repo does not contain a verified bibliography. Do not treat the following topics as claims about prior results; they are the search scope for the literature review.

The first thread is image-based vehicle damage detection and assessment. Search for work that identifies damaged vehicle components from photographs, distinguishes damage categories, and estimates severity. The report should separate object detection or segmentation results from the project's image-level structured claim output. **[CITATION NEEDED: VLMs and computer vision for vehicle damage detection and severity assessment]**

The second thread is prompt design for visual tasks. This project's prompt variants represent a zero-shot structured instruction, a few-shot prompt with two dev examples, and a chain-of-thought-style orientation and panel procedure. A literature review should establish what is known about zero-shot, few-shot, and reasoning prompts for vision-language models, and should avoid assuming that results in general visual QA transfer to vehicle claims. **[CITATION NEEDED: zero-shot, few-shot, and reasoning prompts for vision-language models in visual inspection]**

The third thread is reliable structured generation. Contract A uses finite vocabularies and a Pydantic validator; an optional strict JSON Schema can be passed to the provider. Invalid text or invalid fields are rejected and may receive a text-only repair request. These are engineering choices in this implementation, not evidence that constrained output or repair improves accuracy. The report should cite sources on schema-constrained generation, structured decoding, and validation/repair methods, then distinguish them from the project's measured first-try JSON validity. **[CITATION NEEDED: schema-constrained generation and structured output from language models]** **[CITATION NEEDED: validation and repair of generated JSON]**

The final literature section should explain the gap the project addresses: producing a bounded, machine-readable damage assessment that can be handed to other claim-processing components. No benchmark superiority or clinical/insurance readiness claim is supported by this repository's small evaluation.

### Citation search topics

- VLMs and computer vision for vehicle damage detection and severity assessment.
- Zero-shot, few-shot, and reasoning prompts for VLM-based visual inspection.
- Schema-constrained structured output from language models.
- Validation and repair of generated JSON.

## Methodology

The Role 1 pipeline accepts one to five image inputs, user-provided vehicle details, and an incident description, then returns either a Contract A `DamageReport` or a `VisionError`. The data and prompt setup are documented in `data/cardd_eval/README.md` and `docs/role1/DECISIONS.md`. The scored eval set has 20 images; a separate 10-image dev set supplies two few-shot examples. The labels file marks the eval labels reviewed by Aarti and the dev labels unverified.

The model configurations use Gemini `gemini-3.5-flash-lite` and Qwen `qwen/qwen3.8-27b` through Groq. The planned prompt mapping is: `v1_structured` for zero-shot, `v1_structured` with API schema enforcement for zero-shot plus schema, `v2_fewshot` for few-shot, and `v3_cot` for chain-of-thought. `v0_baseline` and `v4_best` are extra prompt runs; v4 adds explicit orientation, damage-type, and severity rules.

In `src/vision/assess.py`, provider output is parsed and validated as `VisionOutput`. If invalid, the pipeline can make up to two text-only repair attempts. Valid damages from multiple images are merged by `(part, damage_type)`, retaining the more severe entry and highest confidence. Vehicle details are supplied by the user, not inferred from the image. API failures and invalid output can become structured errors; some input validation and prompt-loading exceptions can still escape the original public function. The new byte adapter wraps these operations and returns a report or error dictionary.

Evaluation runs against cached provider responses where available. `eval/metrics.py` computes pooled F1 for damage-type sets and exact/corner-free part F1, as well as validity, retries, latency, token usage, and cost. This report additionally computes exact part-set accuracy per image and bootstrap percentile 95% intervals by resampling images 1,000 times with a fixed seed. A partial configuration is not scored as a completed comparison.

## Results

Seven of the eight planned model/strategy configurations completed a 20-image pass. Qwen v2 reached six images before Groq quota exhaustion. Qwen v1 + schema and Qwen v3 completed all images but include provider-error responses; final validity was 90% and 95%, respectively.

Gemini v4 recorded the top observed damage-type F1 (.925, 95% CI .866–.984), with part exact-set accuracy .700 (95% CI .500–.900). It also used an average 4,979 input and 378 output tokens per image, with 3.328-second latency and $0.002439 per image. Gemini v1 recorded .800 damage-type F1 and .650 exact part match; Qwen v1 recorded .763 and .450, respectively. Their recorded mean latencies were 3.702 and 24.787 seconds, and per-image costs were $0.000996 and $0.003133.

No same-model strategy pair had non-overlapping bootstrap intervals for damage-type F1 or part exact match. The only separated damage-type intervals among all completed configurations were cross-model comparisons involving Gemini v4 and Qwen v0, Qwen v1 + schema, or Qwen v3. Those comparisons cannot isolate prompt effects. The apparent v4 result is optimistic because the prompt was selected after viewing the same eval set. The dev check does not reproduce the v4 eval damage-type score: .667 on 8 images, with exact part match 3/8, versus .925 and 14/20 on eval. The dev labels are not verified.

The per-image records contain 70 predicted opposite-side parts paired with expected parts across the 10 complete configurations; repeats across configurations are counted. The result indicates that side confusion remains a failure mode, not that 70 independent examples failed. The evaluation is exploratory: it does not establish a general model ranking or an improvement that will transfer to a larger claim dataset.
