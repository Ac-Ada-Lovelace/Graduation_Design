# Model Artifact Contract

This contract is the boundary between training and deployment.

## Artifact bundle

A deployable model bundle should contain:

1. `model.onnx`
2. `model_meta.json`
3. `normalization.json`
4. `postprocess.json`

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

## Runtime note

Model output is numeric tensors (`float32`).
The service layer maps tensors into domain JSON (power + events).
