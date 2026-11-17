# Review 3 — Role 1 results

## Results slide

**Headline:** All eight planned runs are complete; the 20-image eval and overlapping intervals do not establish a robust prompt win.

- Gemini v4: damage-type F1 **.925** (95% bootstrap CI **.866–.984**); exact part-set match **.700** (CI **.500–.900**).
- Qwen v2: damage-type F1 **.730** (CI **.581–.850**); exact part-set match **.400** (CI **.200–.600**); **100%** first-try JSON.
- Left/right errors remain: **73** expected-to-opposite-side prediction pairs across 11 completed configurations, counting repeated image/configuration cases.

**Chart:** show `eval/results/metrics_by_config.png`; use `eval/results/part_f1_exact_vs_corner_free.png` if asked about side confusion. State that v4 was selected on the same eval set and the dev check did not reproduce its damage-type score.

## Likely viva questions

1. **Why these prompt versions?**  
   v1 is structured zero-shot, v1 + schema tests provider-side enforcement, v2 adds two dev examples, and v3 asks for an orientation/panel procedure. v0 and v4 are extra runs.

2. **How do you stop malformed output reaching the next role?**  
   Parse and validate against Pydantic; try up to two text-only repairs; return a structured `VisionError` if validation still fails. Provider errors can also return an error object.

3. **Did v4 prove better?**  
   No. It has the highest observed damage-type F1, but it was selected after looking at these eval images. All same-model strategy CIs overlap, and dev v4 scored .667 on 8 images.

4. **How do you define left and right?**  
   They are the vehicle's own sides from a forward-facing driver's perspective. The prompts include this rule; v4 adds view-orientation rules. Despite that, the results contain 73 opposite-side prediction pairs across completed configurations.

5. **What remains incomplete?**  
   The planned eight model/strategy runs are complete. Ten dev labels, including the two few-shot examples, remain unverified; Qwen v1 + schema and v3 include provider-error outputs.
