# Speculative Decoding References

This folder stores the primary-source bundle used for the `Chatterbox T3` speculative-decoding research pass.

## Local PDFs

- `2211.17192_fast_inference_speculative_decoding.pdf`
  - original speculative-decoding paper
  - source: <https://arxiv.org/abs/2211.17192>
- `2309.08168_draft_and_verify.pdf`
  - self-speculative draft-and-verify variant
  - source: <https://arxiv.org/abs/2309.08168>
- `2401.10774_medusa.pdf`
  - multi-head drafting on one backbone
  - source: <https://arxiv.org/abs/2401.10774>
- `2402.02057_lookahead_decoding.pdf`
  - training-free lookahead decoding
  - source: <https://arxiv.org/abs/2402.02057>
- `2024_acl_layerskip.pdf`
  - early-exit / self-speculative decoding
  - source: <https://aclanthology.org/2024.acl-long.681/>
- `Distil_Whisper.pdf`
  - speech-domain adjacent evidence that speculative decoding can work beyond plain text LMs
  - source: <https://arxiv.org/abs/2311.00430>

## Supporting Docs / Repos

- Hugging Face generation strategies:
  - speculative decoding, assistant-model constraints, UAD notes
  - <https://huggingface.co/docs/transformers/generation_strategies>
- vLLM speculative decoding docs:
  - supported speculative methods and current implementation notes
  - <https://docs.vllm.ai/en/latest/features/spec_decode.html>
- Distil-Whisper official repo:
  - assistant-model usage in speech recognition
  - <https://github.com/huggingface/distil-whisper>
- Medusa official repo:
  - practical training/inference details for multi-head drafting
  - <https://github.com/FasterDecoding/Medusa>
- LayerSkip official repo:
  - early-exit self-speculative decoding recipe
  - <https://github.com/facebookresearch/LayerSkip>
