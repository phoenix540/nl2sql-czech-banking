from engine.llm import GroqLLM, list_models


def test_chat_sends_bearer_token(monkeypatch):
    captured = {}

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"choices": [{"message": {"content": "SELECT 1"}, "finish_reason": "stop"}]}

    def fake_post(url, **kwargs):
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr("engine.llm.requests.post", fake_post)
    llm = GroqLLM(api_key="test-token", model="test-model")

    assert llm.chat([{"role": "user", "content": "query"}]) == "SELECT 1"
    assert captured["headers"]["Authorization"] == "Bearer test-token"


def test_list_models_sends_explicit_bearer_token(monkeypatch):
    captured = {}

    class Response:
        @staticmethod
        def raise_for_status():
            pass

        @staticmethod
        def json():
            return {"data": [{"id": "model-b"}, {"id": "model-a"}]}

    def fake_get(url, **kwargs):
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr("engine.llm.requests.get", fake_get)

    assert list_models(api_key="test-token") == ["model-a", "model-b"]
    assert captured["headers"]["Authorization"] == "Bearer test-token"
