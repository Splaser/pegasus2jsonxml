# split_descriptions.py

lines = open("descriptions_raw.jsonl", encoding="utf-8").read().splitlines()

batch_size = 40
for i in range(0, len(lines), batch_size):
    batch = lines[i:i+batch_size]
    open(f"batch_{i//batch_size:03d}.jsonl", "w", encoding="utf-8").write("\n".join(batch))
