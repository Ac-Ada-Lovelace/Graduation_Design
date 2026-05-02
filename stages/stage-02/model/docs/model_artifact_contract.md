# Model Artifact Contract

This contract is the boundary between training and deployment.

## Interface version

- `nilm_model_interface_v1`

All deployable artifacts must satisfy this versioned interface.

## Artifact bundle (required files)

A deployable model bundle should contain:

1. `model.onnx`
2. `model_meta.json`
3. `normalization.json`
4. `postprocess.json`
5. `interface_spec.json` (generated at package-export time)
6. `package_manifest.json` (generated at package-export time)

## `model_meta.json`

Required fields:

- `model_name`: string
- `dataset`: string
- `sample_period_s`: number
- `window_size`: integer
- `appliances`: string[]
- `input_name`: string
- `output_name`: string
- `input_shape`: integer[]
- `output_shape`: integer[]

## `normalization.json`

Required fields:

- `mains_mean`: number
- `mains_std`: number
- `target_mean`: object (appliance -> number)
- `target_std`: object (appliance -> number)

## `postprocess.json`

Required fields:

- `on_threshold_w`: object (appliance -> number)
- `off_threshold_w`: object (appliance -> number)
- `min_on_seconds`: integer
- `min_off_seconds`: integer

Optional fields:

- `linear_calibration`: object (appliance -> `{scale_a, bias_b}`)

## Tensor IO spec

- Input tensor:
  - name: `model_meta.input_name`
  - dtype: `float32`
  - shape: `[batch, window_size, 1]`
  - semantic: 1-second mains window normalized by `normalization.json`
- Output tensor:
  - name: `model_meta.output_name`
  - dtype: `float32`
  - shape: `[batch, N]`, `N = len(model_meta.appliances)`
  - semantic: normalized appliance powers in appliance-order.

## Pre/Post process spec

1. Preprocess:
   - `x_norm = (x - mains_mean) / mains_std`
2. Model inference:
   - ONNX output `y_norm`
3. Denormalization:
   - `y_w = y_norm * target_std + target_mean` (per appliance)
4. Optional linear calibration:
   - if `linear_calibration` exists, apply `y_w = max(0, scale_a * y_w + bias_b)` per appliance
5. Event extraction:
   - use `on_threshold_w/off_threshold_w` and `min_on_seconds/min_off_seconds`

## Swap compatibility rules

A new model package is hot-swappable if all conditions below hold:

1. `interface_spec.interface_version` equals `nilm_model_interface_v1`
2. `sample_period_s` matches caller expectation (current pipeline uses 1 second)
3. Input/output tensor names and rank match runtime adapter
4. Appliance list and order are accepted by downstream business logic
5. Normalization + postprocess files are present and complete

## Runtime note

Model output is numeric tensors (`float32`).
The service layer maps tensors into domain JSON (power + events).
Prefer loading from exported model package zip to avoid drift across files.
