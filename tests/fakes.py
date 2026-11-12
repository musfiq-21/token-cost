"""A fake Ollama backend: no server needed, every request body is recorded."""


class FakeOllama:
    """Callable used as the counter's transport.

    `responder(body)` returns (input_tokens, output_tokens, text, done_reason).
    By default the input count is the length of the user message plus 19 template tokens,
    so English and Bangla prompts of different lengths get different counts.
    """

    def __init__(self, responder=None):
        self.bodies = []
        self.responder = responder or self.default

    @staticmethod
    def default(body):
        user = body["messages"][-1]["content"]
        return 19 + len(user), 7, "answer to " + user, "stop"

    def __call__(self, url, body, timeout):
        self.bodies.append(body)
        inp, out, text, reason = self.responder(body)
        resp = {"message": {"role": "assistant", "content": text}, "done_reason": reason}
        if inp is not None:
            resp["prompt_eval_count"] = inp
        if out is not None:
            resp["eval_count"] = out
        return resp


class FakeClock:
    """Returns the given times in order: perf_counter stand-in."""

    def __init__(self, *times):
        self.times = list(times)

    def __call__(self):
        return self.times.pop(0)


def ticking_clock(step=0.5):
    t = [0.0]

    def clock():
        t[0] += step
        return t[0]
    return clock
