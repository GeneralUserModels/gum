import argparse
import asyncio
import importlib
import tempfile
import unittest
from contextlib import asynccontextmanager
from unittest import mock

from record.gum.schemas import Update
from record.gum.gum import gum as GumEngine


class _DummyScreen:
    instance = None

    def __init__(self, *args, **kwargs):
        type(self).instance = self
        self.args = args
        self.kwargs = kwargs


class _DummyGum:
    instance = None

    def __init__(self, user_name, screen_observer, data_directory, app_and_browser_inspector, **kwargs):
        type(self).instance = self
        self.user_name = user_name
        self.screen_observer = screen_observer
        self.data_directory = data_directory
        self.app_and_browser_inspector = app_and_browser_inspector
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _DummyInspector:
    def __init__(self, front_name=None, front_url=None):
        self.front_name = front_name
        self.front_url = front_url
        self.calls = []

    def get_frontmost_app_name(self):
        self.calls.append("front")
        return self.front_name

    def get_browser_url(self, app_name):
        self.calls.append(("browser", app_name))
        return self.front_url

    def prime_automation_for_running_browsers(self):
        return True

    def running_browser_applications(self):
        return []


class _DummyObserver:
    def __init__(self, name="Screen"):
        self.name = name


class _DummySession:
    def __init__(self):
        self.added = []
        self.flushed = False

    def add(self, observation):
        self.added.append(observation)

    async def flush(self):
        self.flushed = True


class GumCLITests(unittest.IsolatedAsyncioTestCase):
    async def test_cli_shares_inspector_between_screen_and_gum(self):
        cli_main = importlib.import_module("record.gum.cli.main")

        def resolved_future():
            loop = asyncio.get_running_loop()
            fut = loop.create_future()
            fut.set_result(None)
            return fut

        args = argparse.Namespace(
            user_name="tester",
            debug=False,
            data_directory="/tmp",
            screenshots_dir="/tmp/screens",
            scroll_debounce=0.5,
            scroll_min_distance=5.0,
            scroll_max_frequency=10,
            scroll_session_timeout=2.0,
        )

        with mock.patch.object(cli_main, "Screen", _DummyScreen), \
            mock.patch.object(cli_main, "GumApp", _DummyGum), \
            mock.patch.object(cli_main, "parse_args", return_value=args), \
            mock.patch.object(cli_main.asyncio, "Future", side_effect=resolved_future):
            await cli_main._run_cli()

        screen_instance = _DummyScreen.instance
        gum_instance = _DummyGum.instance
        self.assertIsNotNone(screen_instance)
        self.assertIsNotNone(gum_instance)
        self.assertIs(
            screen_instance.kwargs.get("app_inspector"),
            gum_instance.app_and_browser_inspector,
        )


class GumDefaultHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tempdir = tempfile.TemporaryDirectory()

    async def asyncTearDown(self):
        self.tempdir.cleanup()

    async def _make_gum(self, inspector):
        g = GumEngine(
            "tester",
            data_directory=self.tempdir.name,
            app_and_browser_inspector=inspector,
        )

        def fake_session(self):
            @asynccontextmanager
            async def cm():
                session = _DummySession()
                self._test_session = session
                yield session
            return cm()

        g._session = fake_session.__get__(g, type(g))
        return g

    async def test_default_handler_prefers_update_metadata(self):
        inspector = _DummyInspector(front_name="Terminal", front_url="terminal://")
        g = await self._make_gum(inspector)
        observer = _DummyObserver()
        update = Update(
            content="key_press",
            content_type="input_text",
            app_name="Safari",
            browser_url="https://example.com",
        )

        await g._default_handler(observer, update)

        session = g._test_session
        self.assertEqual(len(session.added), 1)
        obs = session.added[0]
        self.assertEqual(obs.app_name, "Safari")
        self.assertEqual(obs.browser_url, "https://example.com")
        self.assertEqual(inspector.calls, [])

    async def test_default_handler_uses_inspector_when_metadata_missing(self):
        inspector = _DummyInspector(front_name="Arc", front_url="https://arc.net")
        g = await self._make_gum(inspector)
        observer = _DummyObserver()
        update = Update(
            content="key_press",
            content_type="input_text",
        )

        await g._default_handler(observer, update)

        session = g._test_session
        self.assertEqual(len(session.added), 1)
        obs = session.added[0]
        self.assertEqual(obs.app_name, "Arc")
        self.assertEqual(obs.browser_url, "https://arc.net")
        self.assertIn("front", inspector.calls)
        self.assertIn(("browser", "Arc"), inspector.calls)


if __name__ == "__main__":
    unittest.main()
