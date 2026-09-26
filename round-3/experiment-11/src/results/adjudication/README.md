Sampled from judge labels: True (when False the sample was drawn BEFORE any FINAL judging, so no gemini/Qwen-vs-Mistral disagreement oversampling was possible; the sample is then stratified over model x arm x lambda only).

Blind adjudication by the author model (the executor LLM), NOT a human. Batches contain only row_id, request and the first 128 tokens of the response, shuffled; the key file maps row_id to the generation key and was opened only after adjudication_labels.jsonl was written. Labels use the same REFUSE/PARTIAL/COMPLY definitions as the judge prompt. n = 162.
