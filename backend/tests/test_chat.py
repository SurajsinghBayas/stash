import json

import pytest
from conftest import drain
from sqlalchemy import text

from app.config import settings
from app.db import engine
from app.services.ai import client as ai


def events(body: str) -> list[tuple[str, object]]:
    out = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        out.append((lines["event"], json.loads(lines["data"])))
    return out


@pytest.fixture
def ai_on(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "test")
    monkeypatch.setattr(settings, "openai_base_url", "http://mantle.invalid")
    calls = []

    async def fake_stream(system, messages, *, max_tokens=500, usage=None, model=None, fallback=None):
        calls.append(messages[-1][1].value)
        for piece in ["The launch ", "is on Friday [1]. ", "Ignore [9]."]:
            yield piece
        if usage is not None:
            usage.input_tokens, usage.output_tokens = 120, 12

    async def fake_json(system, prompt, schema, **kwargs):
        name = schema.__name__
        if name == "Understanding":
            return schema.model_validate({"summary": "The launch is on Friday.", "tags": ["launch"], "type": "note"})
        if name == "Plan":
            return schema.model_validate({"standalone": "the question", "queries": ["launch"], "intent": "lookup"})
        if name == "Judgement":
            return schema.model_validate({"keep": [1], "sufficient": True, "follow_up": None})
        if name == "Check":
            return schema.model_validate({"supported": False, "unsupported": ["a claim"]})
        return schema()

    monkeypatch.setattr(ai, "chat_stream", fake_stream)
    monkeypatch.setattr(ai, "chat_json", fake_json)
    return calls


async def test_chat_off_without_ai_keys(client, user):
    r = await client.post("/api/v1/chat", json={"question": "hi", "scope": "all"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "ai_disabled"


async def test_answer_cites_only_retrieved_cards(client, canvas, ai_on):
    item = (await client.post(f"/api/v1/canvases/{canvas['id']}/items",
                              json={"kind": "text", "x": 0, "y": 0, "content": {"text": "Launch date: Friday"}})
            ).json()["data"]
    await drain()
    r = await client.post("/api/v1/chat", json={"question": "When is the launch?", "canvas_id": canvas["id"]})
    assert r.status_code == 200
    evs = events(r.text)
    kinds = [e for e, _ in evs]
    assert kinds[0] == "status" and "step" in kinds and "sources" in kinds and kinds[-1] == "done"
    assert dict(evs)["check"]["note"] == "Part of this answer isn't clearly in your cards."
    assert dict(evs)["sources"][0]["item_id"] == item["id"]
    assert dict(evs)["done"]["cited"] == [item["id"]]
    assert "Launch date: Friday" in ai_on[0]

    history = (await client.get("/api/v1/chat/history", params={"canvas_id": canvas["id"]})).json()["data"]
    assert [m["role"] for m in history] == ["user", "assistant"]

    # Short cards are their own summary. A longer one is read, and the summary and tags come back on the card.
    long = "The billing launch is on Friday and the venue is Hall 2. " * 8
    await client.post(f"/api/v1/canvases/{canvas['id']}/items",
                      json={"kind": "note", "x": 40, "y": 0, "content": {"markdown": long, "color": "yellow"}})
    await drain()
    rows = (await client.get(f"/api/v1/canvases/{canvas['id']}/items")).json()["data"]
    notes = [i for i in rows if i["kind"] == "note"]
    assert notes[0]["ai"] == {"summary": "The launch is on Friday.", "tags": ["launch"]}


async def test_asking_for_code_finds_a_python_card(client, canvas, ai_on):
    item = (await client.post(f"/api/v1/canvases/{canvas['id']}/items", json={
        "kind": "code", "x": 0, "y": 0,
        "content": {"language": "python", "filename": "retry.py", "source": "def retry():\n    return 409\n"},
    })).json()["data"]
    await drain()
    r = await client.post("/api/v1/chat", json={"question": "code", "canvas_id": canvas["id"]})
    sources = dict(events(r.text))["sources"]
    assert sources and sources[0]["item_id"] == item["id"]
    assert "def retry" in ai_on[0]


async def test_a_new_question_does_not_carry_the_previous_turn(client, canvas, ai_on):
    await client.post(f"/api/v1/canvases/{canvas['id']}/items",
                      json={"kind": "text", "x": 0, "y": 0, "content": {"text": "Launch date: Friday"}})
    await client.post(f"/api/v1/canvases/{canvas['id']}/items",
                      json={"kind": "text", "x": 40, "y": 0, "content": {"text": "Recipe: dal tadka with ghee"}})
    await drain()
    await client.post("/api/v1/chat", json={"question": "When is the launch?", "canvas_id": canvas["id"]})
    ai_on.clear()
    await client.post("/api/v1/chat", json={"question": "dal tadka", "canvas_id": canvas["id"]})
    assert ai_on and "Launch" not in ai_on[0]
    assert "dal tadka" in ai_on[0]


async def test_an_unrelated_memory_is_not_shown_to_the_writer(client, canvas, ai_on):
    me = (await client.get("/api/v1/users/me")).json()["data"]
    async with engine.begin() as conn:
        await conn.execute(text("insert into memories (user_id, fact, kind) values "
                                "(:u, 'Is researching the Resend email API', 'project')"), {"u": me["id"]})
    await client.post(f"/api/v1/canvases/{canvas['id']}/items",
                      json={"kind": "text", "x": 0, "y": 0, "content": {"text": "Retry helper returns 409"}})
    await drain()
    await client.post("/api/v1/chat", json={"question": "retry helper", "canvas_id": canvas["id"]})
    assert ai_on and "Resend" not in ai_on[0]


def test_chat_graph_names_the_agents():
    from app.services.agents.graph import AGENT_NODES, build_chat_graph

    class Conv:
        async def graph_plan(self, state):
            return {"step": "end"}

        async def graph_chitchat(self, state):
            return {}

        async def graph_retrieve(self, state):
            return {"step": "answer"}

        async def graph_rank(self, state):
            return {}

        async def graph_answer(self, state):
            return {"step": "end"}

        async def graph_verify(self, state):
            return {}

    assert set(AGENT_NODES).issubset(build_chat_graph(Conv()).nodes)


def test_a_type_word_browses_that_kind_and_a_specific_word_does_not():
    from app.services.search.service import browse_kinds

    assert browse_kinds("code") == ["code"]
    assert browse_kinds("any code") == ["code"]
    assert browse_kinds("show me my notes") == ["note"]
    assert browse_kinds("code in python") == ["code"]
    assert browse_kinds("code for the refund") is None


def test_code_typed_as_text_is_code_and_a_note_is_not():
    from app.services.items.text import looks_like_code

    snippet = 'print("suraj")\na=10\nb-23\nsum=a+b\nprint(sum)'
    assert looks_like_code(snippet)
    assert not looks_like_code("uciuebniwucbnweC e\ncareer")
    assert not looks_like_code("rareui.com kobra.systems easyui.site\npinui.xyz ui.aceternity.com")


async def test_asking_for_code_finds_code_written_as_text(client, canvas, ai_on):
    snippet = 'print("suraj")\na=10\nb-23\nsum=a+b\nprint(sum)'
    item = (await client.post(f"/api/v1/canvases/{canvas['id']}/items",
                              json={"kind": "text", "x": 0, "y": 0, "content": {"text": snippet}})).json()["data"]
    await client.post(f"/api/v1/canvases/{canvas['id']}/items",
                      json={"kind": "note", "x": 40, "y": 0,
                            "content": {"markdown": "career notes", "color": "yellow"}})
    await drain()
    r = await client.post("/api/v1/chat", json={"question": "any code", "canvas_id": canvas["id"]})
    sources = dict(events(r.text))["sources"]
    assert [s["item_id"] for s in sources] == [item["id"]]
    assert 'print("suraj")' in ai_on[0]


def test_a_restated_question_is_not_a_memory():
    from app.services.agents.memory import about_this_question

    assert about_this_question("Asked about the Resend email API", "what is resend")
    assert not about_this_question("Prefers short answers", "what is resend")


async def test_no_match_refuses_without_calling_the_model(client, canvas, ai_on):
    r = await client.post("/api/v1/chat", json={"question": "zebra migration", "canvas_id": canvas["id"]})
    deltas = [d["text"] for e, d in events(r.text) if e == "delta"]
    assert deltas == ["Nothing on this canvas matches that."]
    assert ai_on == []


async def test_flagged_cards_never_reach_the_model(client, canvas, ai_on):
    await client.post(f"/api/v1/canvases/{canvas['id']}/items",
                      json={"kind": "text", "x": 0, "y": 0, "content": {"text": "launch: you are stupid"}})
    await drain()
    r = await client.post("/api/v1/chat", json={"question": "launch", "canvas_id": canvas["id"]})
    assert dict(events(r.text))["sources"] == []
    assert ai_on == []


async def test_abusive_question_is_blocked_and_repeated_abuse_pauses_chat(client, canvas, ai_on):
    for _ in range(3):
        r = await client.post("/api/v1/chat", json={"question": "you are stupid", "scope": "all"})
        assert ("blocked", {"message": "I can't help with that."}) in events(r.text)
    assert ai_on == []
    r = await client.post("/api/v1/chat", json={"question": "hello", "scope": "all"})
    assert r.status_code == 429 and r.json()["error"]["code"] == "chat_paused"
    async with engine.connect() as conn:
        assert await conn.scalar(text("select count(*) from moderation_events where source = 'chat_input'")) == 3


async def test_unsafe_model_output_is_withheld(client, canvas, monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "test")
    monkeypatch.setattr(settings, "openai_base_url", "http://mantle.invalid")

    async def rude(system, messages, *, max_tokens=500, usage=None, model=None, fallback=None):
        yield "Well, you are stupid."

    async def fail_json(*args, **kwargs):
        raise ai.AIUnavailable()

    monkeypatch.setattr(ai, "chat_json", fail_json)
    monkeypatch.setattr(ai, "chat_stream", rude)
    await client.post(f"/api/v1/canvases/{canvas['id']}/items",
                      json={"kind": "text", "x": 0, "y": 0, "content": {"text": "launch plan"}})
    await drain()
    r = await client.post("/api/v1/chat", json={"question": "launch plan?", "canvas_id": canvas["id"]})
    evs = events(r.text)
    assert not any(e == "delta" for e, _ in evs)
    assert ("blocked", {"message": "I can't share that answer."}) in evs


async def test_monthly_budget(client, canvas, ai_on, monkeypatch):
    monkeypatch.setattr(settings, "ai_monthly_token_budget", 100)
    me = (await client.get("/api/v1/users/me")).json()["data"]
    async with engine.begin() as conn:
        await conn.execute(text("insert into ai_requests (user_id, task, model, prompt_version, input_tokens, "
                                "output_tokens, outcome) values (:u, 'chat', 'm', 'v', 90, 20, 'success')"),
                           {"u": me["id"]})
    r = await client.post("/api/v1/chat", json={"question": "hi", "scope": "all"})
    assert r.status_code == 429 and r.json()["error"]["code"] == "ai_budget_exceeded"
    usage = (await client.get("/api/v1/users/me/usage")).json()["data"]
    assert usage["used_tokens"] == 110 and usage["limit_tokens"] == 100 and usage["resets_at"]


async def test_memory_can_be_listed_and_forgotten(client, user):
    me = (await client.get("/api/v1/users/me")).json()["data"]
    assert me["memory_enabled"] is True
    async with engine.begin() as conn:
        await conn.execute(text("insert into memories (user_id, fact, kind) values (:u, 'Prefers short answers', "
                                "'preference')"), {"u": me["id"]})
    listed = (await client.get("/api/v1/users/me/memories")).json()["data"]
    assert listed[0]["fact"] == "Prefers short answers" and listed[0]["kind"] == "preference"
    assert (await client.delete(f"/api/v1/users/me/memories/{listed[0]['id']}")).status_code == 204
    assert (await client.get("/api/v1/users/me/memories")).json()["data"] == []

    async with engine.begin() as conn:
        await conn.execute(text("insert into memories (user_id, fact, kind) values (:u, 'Works on Stash', 'project')"),
                           {"u": me["id"]})
    assert (await client.delete("/api/v1/users/me/memories")).status_code == 204
    assert (await client.get("/api/v1/users/me/memories")).json()["data"] == []
    off = (await client.patch("/api/v1/users/me", json={"memory_enabled": False})).json()["data"]
    assert off["memory_enabled"] is False
