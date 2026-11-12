"""Token counting: one Ollama /api/chat call -> input and output tokens as Ollama counts them.

Input tokens  = prompt_eval_count (system prompt + chat template + user prompt).
Output tokens = eval_count.

Template overhead: every call uses the same fixed SYSTEM_PROMPT. `overhead()` measures the
tokens that the template and system prompt add by sending an empty user message, so
content tokens = input tokens - overhead.

Prompt caching: Ollama keeps a KV cache, which could in principle make prompt_eval_count
smaller on a repeated prompt. The runner re-counts every prompt after the main run and
records whether the count changed (see runner.py), so the effect is checked, not assumed.
"""
import json
import time
import urllib.request

PRICE_IN_PER_M = 0.15   # notional course prices, USD per million tokens
PRICE_OUT_PER_M = 0.60

# Same for both languages, and deliberately says nothing about which language to answer in.
SYSTEM_PROMPT = "You are a helpful assistant. Answer clearly and concisely."


def cost_usd(input_tokens, output_tokens):
    return input_tokens * PRICE_IN_PER_M / 1e6 + output_tokens * PRICE_OUT_PER_M / 1e6


def bengali_share(text):
    """Share of letters in `text` that are Bengali script (U+0980-U+09FF)."""
    letters = [ch for ch in text if ch.isalpha() or "ঀ" <= ch <= "৿"]
    if not letters:
        return 0.0
    bn = sum(1 for ch in letters if "ঀ" <= ch <= "৿")
    return bn / len(letters)


def _http_post(url, body, timeout):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


class OllamaCounter:
    def __init__(self, model, host="http://localhost:11434", system=SYSTEM_PROMPT,
                 temperature=0, seed=42, num_predict=512, num_ctx=4096, timeout=600,
                 transport=_http_post, clock=time.perf_counter):
        self.model = model
        self.host = host.rstrip("/")
        self.system = system
        self.options = {"temperature": temperature, "seed": seed,
                        "num_predict": num_predict, "num_ctx": num_ctx}
        self.timeout = timeout
        self.transport = transport
        self.clock = clock

    def settings(self):
        return {"model": self.model, "system_prompt": self.system, **self.options}

    def call(self, prompt, num_predict=None):
        options = dict(self.options)
        if num_predict is not None:
            options["num_predict"] = num_predict
        body = {"model": self.model, "stream": False, "options": options,
                "messages": [{"role": "system", "content": self.system},
                             {"role": "user", "content": prompt}]}
        start = self.clock()
        resp = self.transport(self.host + "/api/chat", body, self.timeout)
        latency = self.clock() - start
        if "prompt_eval_count" not in resp or "eval_count" not in resp:
            raise ValueError(f"Ollama response has no token counts: {sorted(resp)}")
        inp, out = int(resp["prompt_eval_count"]), int(resp["eval_count"])
        reason = resp.get("done_reason", "")
        return {"output": resp.get("message", {}).get("content", ""),
                "input_tokens": inp, "output_tokens": out,
                "cost_usd": cost_usd(inp, out), "latency_s": latency,
                "done_reason": reason, "truncated": reason == "length"}

    def overhead(self):
        """Input tokens added by the chat template and system prompt alone."""
        return self.call("", num_predict=1)["input_tokens"]
