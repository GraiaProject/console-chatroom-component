import contextlib
from datetime import datetime
from typing import Any, Dict, Optional, TextIO, cast

from textual.app import App
from textual.binding import Binding
from textual.widgets import Input

from .components.footer import Footer
from .components.header import Header
from .info import Event, MessageEvent
from .log_redirect import FakeIO
from .router import RouterView
from .storage import Storage
from .views.horizontal import HorizontalView
from .views.log_view import LogView
from .backend import Backend


class Frontend(App):
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=False, priority=True),
        Binding("ctrl+d", "toggle_dark", "Toggle dark mode"),
        Binding("ctrl+s", "screenshot", "Save a screenshot"),
        Binding("ctrl+underscore", "focus_input", "Focus input", key_display="ctrl+/"),
    ]

    ROUTES = {"main": lambda: HorizontalView(), "log": lambda: LogView()}

    def __init__(
        self,
        backend: type[Backend],
        title: str = "Console",
        sub_title: str = "powered by Textual"
    ):
        super().__init__()
        self.backend = backend(self)
        self.title = title  # type: ignore
        self.sub_title = sub_title  # type: ignore
        self.storage = Storage()
        self.backend.on_console_init()
        self._fake_output = cast(TextIO, FakeIO(self.storage))
        self._redirect_stdout: Optional[contextlib.redirect_stdout[TextIO]] = None
        self._redirect_stderr: Optional[contextlib.redirect_stderr[TextIO]] = None


    def compose(self):
        yield Header()
        yield RouterView(self.ROUTES, "main")
        yield Footer()

    def on_load(self):
        self.backend.on_console_load()

    def on_mount(self):
        with contextlib.suppress(Exception):
            stdout = contextlib.redirect_stdout(self._fake_output)
            stdout.__enter__()
            self._redirect_stdout = stdout

        with contextlib.suppress(Exception):
            stderr = contextlib.redirect_stderr(self._fake_output)
            stderr.__enter__()
            self._redirect_stderr = stderr

        self.backend.on_console_mount()

    def on_unmount(self):
        if self._redirect_stderr is not None:
            self._redirect_stderr.__exit__(None, None, None)
            self._redirect_stderr = None
        if self._redirect_stdout is not None:
            self._redirect_stdout.__exit__(None, None, None)
            self._redirect_stdout = None
        self.backend.on_console_unmount()

    async def call(self, api: str, data: Dict[str, Any]):
        if api == "send_msg":
            self.storage.write_chat(
                MessageEvent(
                    type="console.message",
                    time=datetime.now(),
                    self_id=data["info"].id,
                    message=data["message"],
                    user=data["info"],
                )
            )
        elif api == "bell":
            await self.run_action("bell")

    def action_focus_input(self):
        with contextlib.suppress(Exception):
            self.query_one(Input).focus()

    async def action_post_message(self, message: str):
        msg = await self.backend.build_message_event(message, self.storage.current_user)
        self.storage.write_chat(msg)
        await self.backend.post_event(msg)

    async def action_post_event(self, event: Event):
        await self.backend.post_event(event)
