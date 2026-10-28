# multilingual-e5-small (quantised ONNX)

The offline text encoder for the contextual match (ADR-0005). It runs on the CPU with `onnxruntime`; page text
never leaves the machine.

- Model: [intfloat/multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small), MIT licence (see `LICENSE`).
- ONNX export and int8 quantisation: [Xenova/multilingual-e5-small](https://huggingface.co/Xenova/multilingual-e5-small), `onnx/model_quantized.onnx`.
- `model_quantized.onnx.001`–`.003` are that file cut into 40 MB parts, because GitHub refuses files over 100 MB.
  The classifier joins them in memory and checks the SHA-256 below.

| File | SHA-256 |
|---|---|
| `model_quantized.onnx` (parts joined) | `f80102d3f2a1229f387d3c81909990d8945513e347b0eab049f7de3c6f98c193` |
| `tokenizer.json` | `0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39` |
| `config.json` | `cb99455288675345e1a4f411438d5d0adbba5fbd3a67ea4fb03c015433b996c1` |
