import json

import httpx
import respx

from app.email import RESEND_BATCH_URL, Email, ResendMailer


def emails(count: int) -> list[Email]:
    return [
        Email(
            to=f"p{n}@example.com",
            subject="Hi",
            text="t",
            html="<p>t</p>",
            headers={"List-Unsubscribe": "<https://x/u>"} if n == 0 else {},
        )
        for n in range(count)
    ]


@respx.mock
async def test_resend_gets_one_email_per_person_in_batches_of_100() -> None:
    route = respx.post(RESEND_BATCH_URL).respond(json={"data": []})
    mailer = ResendMailer("re_test", "App <n@bggroup.app>", "admin@bggroup.app")

    assert await mailer.send(emails(150)) is True

    assert route.call_count == 2
    first = json.loads(route.calls[0].request.content)
    assert len(first) == 100
    assert len(json.loads(route.calls[1].request.content)) == 50
    assert first[0] == {
        "from": "App <n@bggroup.app>",
        "to": ["p0@example.com"],
        "reply_to": ["admin@bggroup.app"],
        "subject": "Hi",
        "text": "t",
        "html": "<p>t</p>",
        "headers": {"List-Unsubscribe": "<https://x/u>"},
    }
    assert "headers" not in first[1]
    assert route.calls[0].request.headers["Authorization"] == "Bearer re_test"


@respx.mock
async def test_a_failed_send_is_reported_not_raised() -> None:
    respx.post(RESEND_BATCH_URL).respond(422, json={"message": "bad"})
    mailer = ResendMailer("re_test", "n@bggroup.app", "")

    assert await mailer.send(emails(1)) is False


@respx.mock
async def test_an_unreachable_resend_is_reported_not_raised() -> None:
    respx.post(RESEND_BATCH_URL).mock(side_effect=httpx.ConnectError("down"))
    mailer = ResendMailer("re_test", "n@bggroup.app", "")

    assert await mailer.send(emails(1)) is False
    assert await mailer.send([]) is True
