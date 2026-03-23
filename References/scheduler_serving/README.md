# Scheduler Serving References

This folder contains the primary scheduler / serving references for the current `T3` mixed-traffic work.

## Papers

- `Orca_OSDI22.pdf`
  - Official paper URL: `https://www.usenix.org/system/files/osdi22-yu.pdf`
  - Why it matters: canonical iteration-level scheduling and selective batching reference.

- `vLLM_PagedAttention_2309.06180.pdf`
  - Official paper URL: `https://arxiv.org/pdf/2309.06180.pdf`
  - Why it matters: best practical continuous-batching and request-local KV-cache reference.

- `Sarathi-Serve_OSDI24.pdf`
  - Official paper URL: `https://www.usenix.org/system/files/osdi24-agrawal.pdf`
  - Why it matters: strongest paper for staggered mixed-length traffic, chunked prefill, and decode-friendly scheduling.

- `FastServe_2305.05920.pdf`
  - Official paper URL: `https://arxiv.org/pdf/2305.05920.pdf`
  - Why it matters: preemptive scheduling and fairness-oriented serving for AR decode.

- `SGLang_2312.07104.pdf`
  - Official paper URL: `https://arxiv.org/pdf/2312.07104.pdf`
  - Why it matters: modern serving runtime with continuous batching and a low-overhead scheduler.

- `DistServe_OSDI24.pdf`
  - Official paper URL: `https://www.usenix.org/system/files/osdi24-zhong-yinmin.pdf`
  - Why it matters: relevant later if prefill/decode disaggregation becomes necessary.

- `Llumnix_2406.03243.pdf`
  - Official paper URL: `https://arxiv.org/pdf/2406.03243.pdf`
  - Why it matters: dynamic cross-instance rescheduling reference, useful if the current work grows into multi-instance serving.

## Related Repos In `external/`

- `external/vllm/`
- `external/sglang/`
- `external/sarathi-serve/`
- `external/FastServe/`
- `external/TensorRT-LLM/`
- `external/DistServe/`
- `external/llumnix-ray/`
- `external/triton-server/`
