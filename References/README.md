# References Bundle

This folder contains the primary references used to trace the `S3 token -> mel` lineage and scaling limits.

It now also includes a scheduler-serving sub-bundle for the current `T3` mixed-traffic research:

- `scheduler_serving/README.md`
  - Why it matters: local bundle for `Orca`, `vLLM`, `Sarathi-Serve`, `FastServe`, `SGLang`, `DistServe`, and `Llumnix` as prior art for continuous batching and mixed-length real-time scheduling.

## Papers

- `CosyVoice_v1.pdf`
  - Official paper URL: `https://funaudiollm.github.io/pdf/CosyVoice_v1.pdf`
  - Why it matters: first published system in this chain that clearly combines supervised semantic speech tokens, prompt conditioning, speaker conditioning, and a token-to-mel conditional flow decoder.

- `CosyVoice2_2412.10117.pdf`
  - Official paper URL: `https://arxiv.org/pdf/2412.10117.pdf`
  - Why it matters: evolves the same idea toward streaming with finite-scalar-quantized speech tokens and chunk-aware causal flow matching.

- `CozyVoice3.pdf`
  - Official paper URL: `https://arxiv.org/pdf/2505.17589.pdf`
  - Why it matters: later CosyVoice-family evolution focused on in-the-wild quality, post-training, and bi-streaming deployment. It changes the flow stack, but does not remove the core autoregressive speech-token LM plus iterative flow-decoder structure.

- `Matcha-TTS_2309.03199.pdf`
  - Official paper URL: `https://arxiv.org/pdf/2309.03199.pdf`
  - Why it matters: direct flow-decoder ancestor of the CosyVoice acoustic model.

- `Grad-TTS_2105.06337.pdf`
  - Official paper URL: `https://arxiv.org/pdf/2105.06337.pdf`
  - Why it matters: earlier iterative mel-generation ancestor using diffusion.

- `Glow-TTS_2005.11129.pdf`
  - Official paper URL: `https://arxiv.org/pdf/2005.11129.pdf`
  - Why it matters: earlier alignment-driven non-autoregressive text-to-mel ancestor.

- `Flow_Matching_2210.02747.pdf`
  - Official paper URL: `https://arxiv.org/pdf/2210.02747.pdf`
  - Why it matters: generic flow-matching method that Matcha-TTS builds on.

## Repos

- `Matcha-TTS_repo/`
  - Official repo URL: `https://github.com/shivammehta25/Matcha-TTS`
  - Why it matters: local code reference for the decoder and flow-matching stack that CosyVoice builds on.

## Already Available Elsewhere In This Workspace

These were part of the same research pass but already live outside this folder:

- `external/CosyVoice/`
- `external/chatterbox/`
- `architecture/s3_origin_story.html`
- `architecture/cosyvoice2_vs_3_scaling.html`

Those are not duplicated here.
