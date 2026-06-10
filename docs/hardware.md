# Hardware Guidance

The baseline target is a weaker home PC, for example GTX 1080 with 16 GB system RAM.

## Practical Defaults

- Prefer 3B-8B models for interactive use.
- Prefer Q4/Q5 quantized models.
- Keep context at 4K or 8K unless the task really needs more.
- Run one loaded model at a time on the weak machine.
- Keep `max_tokens` modest for routine agents.
- Prefer small specialist agents over one large general model.

## GTX 1080 Notes

GTX 1080 can still be useful, but it is an older CUDA GPU without modern tensor acceleration. Expect quantized inference to be acceptable for small models and slower for larger ones.

Recommended use:

- fast chat, notes, summarization: 3B-4B Q4/Q5;
- coding help: 7B-8B Q4 if responsiveness is acceptable;
- heavy reasoning, long context, larger coding models: remote LAN node.

## Memory Budget

For 16 GB RAM:

- leave headroom for the OS and browser;
- avoid multiple model processes;
- avoid very large context windows;
- keep model files on SSD;
- prefer runtimes that can unload idle models.

## Model Routing Strategy

Use local models for low-latency daily tasks:

- quick chat;
- short summarization;
- rewriting;
- local notes;
- simple code explanations.

Use LAN nodes for:

- bigger coding models;
- longer context;
- batch jobs;
- embeddings or indexing;
- multimodal models.
