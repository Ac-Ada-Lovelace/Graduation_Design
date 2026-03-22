# Stage 02 Decision Snapshot (2026-03-22)

## Purpose

Record the agreed decisions from the recent design discussion.

## Agreed Decisions

1. Stage-02 target is a deployable NILM inference foundation:
   model training + export + online inference + demo loop.

2. Stage-02 module structure:
   - model/
   - service/
   - replay/
   - ui/
   - integration/

3. UK-DALE mainline granularity:
   - training supervision: 6s (stability first)
   - demo refresh: 1s (experience first)

4. Model strategy:
   - single-appliance single-model for kettle/microwave/fridge
   - all models consume the same mains window in parallel

5. Online inference behavior:
   - do not wait to know which appliance is ON
   - always run target models, then infer ON/OFF from predicted power

6. Service output shape:
   - pred_w (per-appliance power)
   - events (on/off etc. from rule-based postprocess)

7. Environment split:
   - this machine: spec/planning/code skeleton
   - training machine: data processing/training/export

## Next Implementation Focus

1. Fix model config to 6s training baseline.
2. Add train/export script skeletons for remote training machine.
3. Keep artifact contract as the deployment boundary.
