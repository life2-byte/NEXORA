# count_tokens.py
#
# Counts tokens in the datasets WITHOUT downloading the complete datasets
# to disk. Data is streamed from Hugging Face.
#
# Tokenizer used: GPT-2 BPE, so all numbers are comparable.

from datasets import load_dataset
from transformers import AutoTokenizer
import time

TOKENIZER = "gpt2"

DATASETS = {
    "FineWeb-Edu": {
        "name": "HuggingFaceFW/fineweb-edu",
        "config": "sample-10BT",
        "split": "train",
        "field": "text",
    },
    "Stack-Edu": {
        "name": "HuggingFaceTB/stack-edu",
        "config": None,
        "split": "train",
        "field": "content",
    },
    "SmolTalk": {
        "name": "HuggingFaceTB/smoltalk",
        "config": "all",
        "split": "train",
        "field": "messages",
    },
}


def count_tokens(tokenizer, dataset_info):
    kwargs = {
        "path": dataset_info["name"],
        "split": dataset_info["split"],
        "streaming": True,
    }

    if dataset_info["config"] is not None:
        kwargs["name"] = dataset_info["config"]

    ds = load_dataset(**kwargs)

    total = 0
    examples = 0
    start = time.time()

    for row in ds:
        value = row[dataset_info["field"]]

        # SmolTalk stores conversations as a list of messages.
        if isinstance(value, list):
            text = "\n".join(
                str(m.get("content", ""))
                for m in value
                if isinstance(m, dict)
            )
        else:
            text = str(value)

        total += len(tokenizer.encode(text, add_special_tokens=False))
        examples += 1

        if examples % 10000 == 0:
            elapsed = time.time() - start
            rate = total / max(elapsed, 1)

            print(
                f"\r  examples: {examples:,} | "
                f"tokens: {total:,} | "
                f"{rate:,.0f} tok/s",
                end="",
                flush=True,
            )

    print()

    return examples, total


def main():
    print("=" * 70)
    print("DATASET TOKEN COUNTER")
    print("=" * 70)
    print(f"Tokenizer: {TOKENIZER}")
    print("Mode: STREAMING")
    print()

    tokenizer = AutoTokenizer.from_pretrained(TOKENIZER)

    grand_total = 0

    for name, info in DATASETS.items():
        print(f"\n[{name}]")
        print("-" * 70)

        try:
            examples, tokens = count_tokens(tokenizer, info)

            grand_total += tokens

            print(f"Examples : {examples:,}")
            print(f"Tokens   : {tokens:,}")

        except Exception as e:
            print(f"ERROR: {e}")

    print("\n" + "=" * 70)
    print("COMBINED TOTAL")
    print("=" * 70)
    print(f"{grand_total:,} GPT-2 tokens")
    print(f"{grand_total / 1_000_000_000:.3f} Billion tokens")
    print(f"{grand_total / 1_000_000_000_000:.6f} Trillion tokens")
    print("=" * 70)


if __name__ == "__main__":
    main()