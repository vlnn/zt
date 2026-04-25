"""
Faithful pure-Python forward pass for z80ai's tinychat model, matching the
Z80 binary's actual semantics:

  1. Input bucket-counts scaled by 32 (ACTIVATION_SCALE).
  2. Per layer:
     a. Dot product of int8 weights {-2,-1,0,+1} with int16 activations.
     b. Add int16 bias.
     c. 16-bit signed wraparound (matches the Z80 16-bit accumulator).
     d. Arithmetic right shift by 2 (matches `sra h; rr l` × 2; this is
        FLOOR division by 4, NOT truncation — feedme.py's _forward_int
        uses trunc, which disagrees with the actual Z80 binary).
     e. ReLU on hidden layers; raw on the final layer.
  3. Argmax across the final 40-class logits.
  4. Lookup in charset; NUL = EOS = stop generating.

Autoregressive loop: query encoded once; context encoded each step from the
characters generated so far (padded to context_len=8 with leading spaces).
"""
from __future__ import annotations

import sys
from pathlib import Path


def hash_trigram(trigram: str, num_buckets: int = 128) -> int:
    h = 0
    for c in trigram:
        h = (h * 31 + ord(c)) & 0xFFFF
    return h % num_buckets


def encode_query(text: str, num_buckets: int = 128) -> list[int]:
    vec = [0] * num_buckets
    padded = " " + text.lower() + " "
    for i in range(len(padded) - 2):
        vec[hash_trigram(padded[i:i + 3], num_buckets)] += 1
    return vec


def hash_ngram(ngram: str, offset: int, num_buckets: int = 128) -> int:
    h = (offset * 7) & 0xFFFF
    for c in ngram:
        h = (h * 31 + ord(c)) & 0xFFFF
    return h % num_buckets


def encode_context(recent: str, num_buckets: int = 128, context_len: int = 8) -> list[int]:
    vec = [0] * num_buckets
    tail = recent[-context_len:].lower()
    padded = tail.rjust(context_len)
    for n in (1, 2, 3):
        for i in range(len(padded) - n + 1):
            vec[hash_ngram(padded[i:i + n], i, num_buckets)] += 1
    return vec


def to_int16(x: int) -> int:
    x = x & 0xFFFF
    return x - 0x10000 if x >= 0x8000 else x


def arshift2(x: int) -> int:
    return x >> 2 if x >= 0 else -((-x + 3) >> 2)


def _arshift2_floor(x: int) -> int:
    return x >> 2


def forward_z80(input_vec, layers):
    activations = [v * 32 for v in input_vec]
    final_idx = len(layers) - 1
    for li, (weights, biases) in enumerate(layers):
        next_acts = []
        for row, b in zip(weights, biases):
            acc = sum(int(w) * int(a) for w, a in zip(row, activations))
            acc += int(b)
            acc = to_int16(acc)
            acc = _arshift2_floor(acc)
            if li < final_idx:
                acc = max(0, acc)
            next_acts.append(acc)
        activations = next_acts
    return activations


def load_layers(npz_path: str):
    import numpy as np
    data = np.load(npz_path, allow_pickle=False)
    layers = []
    i = 1
    while f"fc{i}_weight" in data:
        weights = data[f"fc{i}_weight"].tolist()
        biases = data[f"fc{i}_bias"].tolist()
        layers.append((weights, biases))
        i += 1
    charset = bytes(data["_charset"]).decode("latin-1")
    return layers, charset


def predict_next_char(query_text: str, generated_so_far: str, layers, charset):
    query_vec = encode_query(query_text)
    context_vec = encode_context(generated_so_far)
    input_vec = query_vec + context_vec
    logits = forward_z80(input_vec, layers)
    idx = max(range(len(logits)), key=lambda i: logits[i])
    return idx, charset[idx], logits


def generate(query_text: str, layers, charset, max_chars: int = 32):
    out = ""
    for _ in range(max_chars):
        idx, ch, _ = predict_next_char(query_text, out, layers, charset)
        if ch == "\x00":
            break
        out += ch
    return out


if __name__ == "__main__":
    npz = sys.argv[1] if len(sys.argv) > 1 else "/tmp/z80ai/examples/tinychat/model.npz"
    layers, charset = load_layers(npz)
    print(f"loaded model: {len(layers)} layers, charset={charset!r}")
    print()
    for query in ["hello", "are you a robot", "do you dream", "who are you", "what is your name"]:
        out = generate(query, layers, charset)
        print(f"  > {query}")
        print(f"  {out}")
        print()
