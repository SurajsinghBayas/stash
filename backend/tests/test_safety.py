import pytest

from app.services.ai import client as ai
from app.services.links.fetch import BlockedURL, _check_host
from app.services.safety.service import SafeText, authored, check_text


async def test_wordlist_blocks_including_leetspeak():
    assert not (await check_text("y0u are stup1d", "input")).ok
    assert (await check_text("a normal note about cooking", "input")).ok


async def test_safe_text_cannot_be_forged():
    with pytest.raises(TypeError):
        SafeText("anything", object())


async def test_ai_clients_refuse_plain_strings():
    with pytest.raises(TypeError):
        await ai.embed(["plain string"], "query")  # type: ignore[list-item]
    with pytest.raises(TypeError):
        async for _ in ai.chat_stream(authored("system"), [("user", "plain")]):  # type: ignore[list-item]
            pass


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/", "http://localhost/", "http://169.254.169.254/latest/meta-data/", "http://10.0.0.5/",
    "http://[::1]/", "ftp://example.com/", "http://example.com:8080/", "https://xvideos.com/",
])
async def test_link_fetch_blocks_private_and_adult_targets(url):
    with pytest.raises(BlockedURL):
        await _check_host(url)
