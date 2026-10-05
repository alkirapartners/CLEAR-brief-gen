"""Stand-ins for the Anthropic client. Nothing here touches the network."""

from types import SimpleNamespace

import anthropic
import httpx


def timed_out():
    """The error the SDK raises when a request to the model runs out of time."""
    return anthropic.APITimeoutError(request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))


def usage(input_tokens=100, output_tokens=20, cache_read=0, cache_write=0):
    return SimpleNamespace(
        input_tokens=input_tokens, output_tokens=output_tokens,
        cache_read_input_tokens=cache_read, cache_creation_input_tokens=cache_write,
        cache_creation=None,
    )


def text(value):
    return SimpleNamespace(type="text", text=value)


def thinking():
    return SimpleNamespace(type="thinking", thinking="")


def tool_use(call_id, name, tool_input):
    return SimpleNamespace(type="tool_use", id=call_id, name=name, input=tool_input)


def reply(*blocks, stop_reason=None, stop_details=None, used=None):
    """A model reply. It stops for tool use when it holds a tool call."""
    has_call = any(block.type == "tool_use" for block in blocks)
    return SimpleNamespace(
        content=list(blocks),
        stop_reason=stop_reason or ("tool_use" if has_call else "end_turn"),
        stop_details=stop_details,
        usage=used or usage(),
    )


class FakeStream:
    """What ``client.beta.messages.stream(...)`` returns: events, then a message."""

    def __init__(self, message, events, on_event=None):
        self.message, self.events, self.on_event = message, events, on_event
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.closed = True
        return False

    def __iter__(self):
        for event in self.events:
            if self.on_event is not None:
                self.on_event()
            yield event

    def get_final_message(self):
        return self.message


def block_start(block_type):
    return SimpleNamespace(type="content_block_start", content_block=SimpleNamespace(type=block_type))


class FakeClient:
    """Plays research turns from a script and answers the writer call.

    ``turns`` are returned one per research request; when they run out,
    ``then`` is returned for every further request. A turn that is an
    exception is raised instead. ``on_request`` is called before each
    research request with its number, and ``on_writer_event`` before each
    event of the writer's stream, so a test can move a clock.
    """

    def __init__(self, turns=(), then=None, writer=None, on_request=None, on_writer_event=None):
        self.turns = list(turns)
        self.then = then or reply(text("Research complete."))
        self.writer = writer
        self.on_request = on_request
        self.on_writer_event = on_writer_event
        self.stream = None
        self.requests, self.writer_requests = [], []
        # What each ``with_options`` call asked for, in order: one per request.
        self.options = []
        self.beta = SimpleNamespace(
            messages=SimpleNamespace(create=self._create, stream=self._stream)
        )

    def with_options(self, **options):
        self.options.append(options)
        return self

    def _create(self, **kwargs):
        self.requests.append(kwargs)
        if self.on_request is not None:
            self.on_request(len(self.requests))
        turn = self.turns.pop(0) if self.turns else self.then
        if isinstance(turn, BaseException):
            raise turn  # a scripted failure, such as a timeout
        return turn

    def _stream(self, **kwargs):
        self.writer_requests.append(kwargs)
        events = [block_start(block.type) for block in self.writer.content]
        self.stream = FakeStream(self.writer, events, self.on_writer_event)
        return self.stream
