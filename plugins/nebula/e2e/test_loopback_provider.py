"""The synthetic loopback provider never advertises a non-test model ID."""
import json
import urllib.request

from support.loopback_provider import LoopbackProvider


def test_loopback_provider_uses_explicit_test_model_id():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with LoopbackProvider() as provider:
        with opener.open(provider.base_url + "/models", timeout=3) as response:
            models = json.loads(response.read().decode("utf-8"))
        assert models["data"] == [{"id": "e2e-test-model", "object": "model"}]

        request = urllib.request.Request(
            provider.base_url + "/chat/completions",
            data=json.dumps({
                "model": "e2e-test-model",
                "stream": True,
                "messages": [{"role": "user", "content": "local e2e test"}],
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with opener.open(request, timeout=3) as response:
            lines = response.read().decode("utf-8").splitlines()
        events = [
            json.loads(line[6:])
            for line in lines
            if line.startswith("data: ") and line != "data: [DONE]"
        ]
        assert events
        assert all(event["model"] == "e2e-test-model" for event in events)
