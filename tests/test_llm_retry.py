from loan_agent.llm import LLMError, _RetryingLLM


class Flaky(_RetryingLLM):
    """Fails `fails` times with the given status code, then answers."""
    name = "flaky"

    def __init__(self, fails, code):
        super().__init__(max_retries=3, base_delay=0)
        self.fails, self.code = fails, code

    def _call(self, prompt, as_json):
        if self.fails:
            self.fails -= 1
            e = RuntimeError("boom"); e.code = self.code
            raise e
        return '{"ok": true}'

    def _status(self, exc):
        return getattr(exc, "code", None)


def test_retries_rate_limit_and_network_errors():
    assert Flaky(2, 429).json("x") == {"ok": True}
    assert Flaky(2, None).json("x") == {"ok": True}  # network error: no HTTP code


def test_does_not_retry_bad_request():
    llm = Flaky(1, 400)
    try:
        llm.json("x")
        assert False
    except LLMError:
        assert llm.calls == 1


def test_gives_up_after_max_retries():
    llm = Flaky(10, 503)
    try:
        llm.json("x")
        assert False
    except LLMError:
        assert llm.calls == 4
