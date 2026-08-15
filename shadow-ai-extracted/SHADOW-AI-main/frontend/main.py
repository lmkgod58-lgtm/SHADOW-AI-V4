import json
import os
import uuid

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Line, Rectangle, RoundedRectangle
from kivy.metrics import dp
from kivy.network.urlrequest import UrlRequest
from kivy.properties import BooleanProperty, NumericProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.video import Video
from kivy.uix.widget import Widget
from kivy.uix.floatlayout import FloatLayout


# ============================================================
# SHADOW AI 3.0 - FRONTEND
# ============================================================
# Railway URL is the BASE URL. Do not add /chat here.
BACKEND_URL = "https://shadow-ai-production-aa93.up.railway.app"
BACKGROUND_IMAGE = "background.jpg"
INTRO_VIDEO = "intro.mp4"  # Optional: place your chosen MP4 beside main.py.

ACCENT = (0.35, 1.0, 0.78, 1)
ACCENT_SOFT = (0.12, 0.65, 0.48, 1)
BG = (0.025, 0.02, 0.07, 1)
PANEL = (0.035, 0.04, 0.085, 0.94)
TEXT = (0.94, 0.97, 1, 1)
MUTED = (0.50, 0.58, 0.68, 1)


class GlowButton(Button):
    def __init__(self, **kwargs):
        super().__init__(background_normal="", background_down="", **kwargs)
        self.background_color = (0, 0, 0, 0)
        self._pressed = False
        with self.canvas.before:
            self.glow_outer = Color(ACCENT[0], ACCENT[1], ACCENT[2], 0.10)
            self.outer = RoundedRectangle(radius=[dp(15)])
            self.glow_inner = Color(ACCENT[0], ACCENT[1], ACCENT[2], 0.20)
            self.inner = RoundedRectangle(radius=[dp(13)])
        with self.canvas.after:
            self.border_color = Color(ACCENT[0], ACCENT[1], ACCENT[2], 0.55)
            self.border = Line(rounded_rectangle=(0, 0, 0, 0, dp(14)), width=1.0)
        self.bind(pos=self._draw, size=self._draw)

    def _draw(self, *_):
        self.outer.pos = (self.x - dp(3), self.y - dp(3))
        self.outer.size = (self.width + dp(6), self.height + dp(6))
        self.inner.pos = self.pos
        self.inner.size = self.size
        self.border.rounded_rectangle = (self.x, self.y, self.width, self.height, dp(14))


class MessageBubble(BoxLayout):
    def __init__(self, text, is_user=False, **kwargs):
        super().__init__(orientation="vertical", size_hint=(None, None), padding=(dp(15), dp(11)), **kwargs)
        self.is_user = is_user
        self.max_width = max(dp(260), Window.width * (0.79 if is_user else 0.84))
        self.width = self.max_width

        self.role_label = Label(
            text="YOU" if is_user else "SHADOW AI",
            color=ACCENT if is_user else (0.55, 0.72, 1, 1),
            font_size="9sp",
            bold=True,
            size_hint_y=None,
            height=dp(16),
            halign="left",
            valign="middle",
        )
        self.message = Label(
            text=str(text),
            color=TEXT,
            font_size="15sp",
            line_height=1.18,
            halign="left",
            valign="top",
            size_hint=(1, None),
            text_size=(self.width - dp(30), None),
        )
        self.message.bind(texture_size=self._update_height)
        self.add_widget(self.role_label)
        self.add_widget(self.message)

        with self.canvas.before:
            self.glow = Color(ACCENT[0], ACCENT[1], ACCENT[2], 0.07 if is_user else 0.035)
            self.glow_rect = RoundedRectangle(radius=[dp(22)])
            self.fill = Color(0.05, 0.09, 0.14, 0.96) if is_user else Color(0.025, 0.035, 0.065, 0.96)
            self.rect = RoundedRectangle(radius=[dp(19)])
        with self.canvas.after:
            self.edge = Color(ACCENT[0], ACCENT[1], ACCENT[2], 0.58 if is_user else 0.22)
            self.line = Line(rounded_rectangle=(0, 0, 0, 0, dp(19)), width=1.05)
        self.bind(pos=self._draw, size=self._draw)
        Clock.schedule_once(self._update_height, 0)

    def _update_height(self, *_):
        self.message.text_size = (max(dp(80), self.width - dp(30)), None)
        self.height = self.message.texture_size[1] + self.role_label.height + dp(22)
        self._draw()

    def _draw(self, *_):
        self.glow_rect.pos = (self.x - dp(3), self.y - dp(3))
        self.glow_rect.size = (self.width + dp(6), self.height + dp(6))
        self.rect.pos = self.pos
        self.rect.size = self.size
        self.line.rounded_rectangle = (self.x, self.y, self.width, self.height, dp(19))

    def set_width(self, width):
        self.width = width
        self._update_height()


class MessageRow(BoxLayout):
    def __init__(self, bubble, is_user=False, **kwargs):
        super().__init__(orientation="horizontal", size_hint_y=None, padding=(dp(10), dp(5)), spacing=dp(5), **kwargs)
        if is_user:
            self.add_widget(Widget())
            self.add_widget(bubble)
        else:
            self.add_widget(bubble)
            self.add_widget(Widget())
        self.bubble = bubble
        self.bind(minimum_height=self.setter("height"))


class ThinkingBubble(MessageBubble):
    def __init__(self):
        super().__init__("Thinking", is_user=False)
        self.t = 0
        self._event = Clock.schedule_interval(self.animate, 0.35)

    def animate(self, *_):
        self.t = (self.t + 1) % 4
        self.message.text = "Thinking" + "." * self.t

    def stop(self):
        if self._event:
            self._event.cancel()
            self._event = None


class ShadowAI(App):
    busy = BooleanProperty(False)
    deep_search = BooleanProperty(False)

    def build(self):
        self.title = "Shadow AI"
        Window.clearcolor = BG
        Window.softinput_mode = "resize"
        self.history = []
        self.royal_mode = False
        self.user_id = self._load_user_id()
        self.thinking_row = None
        self.glow_phase = 0

        root = FloatLayout()
        self.root_layout = root

        # Background image + dark cinematic overlay.
        if os.path.exists(BACKGROUND_IMAGE):
            self.background = Image(source=BACKGROUND_IMAGE, allow_stretch=True, keep_ratio=False, opacity=0.26)
            root.add_widget(self.background)
        with root.canvas.after:
            Color(0.015, 0.015, 0.045, 0.58)
            self.screen_overlay = Rectangle(pos=root.pos, size=root.size)
        root.bind(pos=self._root_draw, size=self._root_draw)

        interface = BoxLayout(orientation="vertical", padding=(dp(9), 0, dp(9), dp(8)))
        root.add_widget(interface)

        self._build_header(interface)
        self._build_chat(interface)
        self._build_composer(interface)

        self.add_message(
            "Welcome to Shadow AI.\n\n"
            "Talk normally, ask questions, research topics, compare options, build things, or get advice.\n\n"
            "✦ Deep research can combine multiple public sources.\n"
            "✦ Type 666(LINDO) to activate Royal Mode."
        )

        # Do not auto-focus. That was causing the keyboard to appear before the user was ready.
        Clock.schedule_once(lambda *_: self.check_backend(), 0.6)
        Clock.schedule_interval(self._animate_glow, 0.05)

        # Optional cinematic intro.
        Clock.schedule_once(lambda *_: self.play_intro(root), 0.15)
        return root

    def _root_draw(self, *_):
        self.screen_overlay.pos = self.root_layout.pos
        self.screen_overlay.size = self.root_layout.size

    def _build_header(self, parent):
        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(78), padding=(dp(12), dp(9)), spacing=dp(9))
        with header.canvas.before:
            Color(0.015, 0.02, 0.055, 0.96)
            header_bg = RoundedRectangle(radius=[0, 0, dp(22), dp(22)])
            Color(ACCENT[0], ACCENT[1], ACCENT[2], 0.14)
            header_line = Line(rounded_rectangle=(0, 0, 0, 0, dp(20)), width=1)
        header.bind(pos=lambda *_: self._header_draw(header, header_bg, header_line), size=lambda *_: self._header_draw(header, header_bg, header_line))

        title = BoxLayout(orientation="vertical", spacing=0)
        self.title_label = Label(text="SHADOW AI", font_size="21sp", bold=True, color=ACCENT, halign="left", valign="middle")
        self.subtitle = Label(text="CONNECTING • NEURAL GATEWAY", font_size="9sp", color=MUTED, halign="left", valign="top")
        title.add_widget(self.title_label)
        title.add_widget(self.subtitle)
        header.add_widget(title)

        self.research_button = GlowButton(text="✦", font_size="19sp", size_hint_x=None, width=dp(48), color=TEXT)
        self.research_button.bind(on_press=self.toggle_research)
        header.add_widget(self.research_button)

        new_chat = GlowButton(text="＋", font_size="22sp", size_hint_x=None, width=dp(48), color=TEXT)
        new_chat.bind(on_press=self.new_chat)
        header.add_widget(new_chat)
        parent.add_widget(header)

    def _header_draw(self, header, bg, line):
        bg.pos, bg.size = header.pos, header.size
        line.rounded_rectangle = (header.x, header.y, header.width, header.height, dp(20))

    def _build_chat(self, parent):
        self.scroll = ScrollView(do_scroll_x=False, bar_width=dp(3), scroll_type=["content", "bars"])
        self.chat = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(2), padding=(dp(2), dp(10), dp(2), dp(18)))
        self.chat.bind(minimum_height=self.chat.setter("height"))
        self.scroll.add_widget(self.chat)
        parent.add_widget(self.scroll)

        # A subtle lower fade gives the composer a cleaner separation.
        self.status = Label(text="READY", size_hint_y=None, height=dp(22), font_size="9sp", color=MUTED, halign="center")
        parent.add_widget(self.status)

    def _build_composer(self, parent):
        self.composer = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(72), padding=(dp(6), dp(7)), spacing=dp(7))
        with self.composer.canvas.before:
            Color(0.015, 0.02, 0.055, 0.98)
            self.composer_bg = RoundedRectangle(radius=[dp(20)])
            Color(ACCENT[0], ACCENT[1], ACCENT[2], 0.16)
            self.composer_line = Line(rounded_rectangle=(0, 0, 0, 0, dp(19)), width=1)
        self.composer.bind(pos=self._composer_draw, size=self._composer_draw)

        self.input = TextInput(
            hint_text="Message Shadow AI…",
            multiline=True,
            background_normal="",
            background_active="",
            background_color=(0.035, 0.05, 0.09, 1),
            foreground_color=TEXT,
            hint_text_color=(0.38, 0.45, 0.55, 1),
            cursor_color=ACCENT,
            selection_color=(ACCENT[0], ACCENT[1], ACCENT[2], 0.22),
            padding=(dp(13), dp(10)),
            font_size="15sp",
            write_tab=False,
        )
        self.input.bind(text=self._input_changed, focus=self._input_focus)
        self.composer.add_widget(self.input)

        self.send_button = GlowButton(text="➤", font_size="22sp", bold=True, size_hint_x=None, width=dp(57), color=TEXT)
        self.send_button.bind(on_press=self.send_message)
        self.composer.add_widget(self.send_button)
        parent.add_widget(self.composer)

    def _composer_draw(self, *_):
        self.composer_bg.pos, self.composer_bg.size = self.composer.pos, self.composer.size
        self.composer_line.rounded_rectangle = (self.composer.x, self.composer.y, self.composer.width, self.composer.height, dp(19))

    def _input_changed(self, *_):
        # Grow the composer for 1-4 lines while remaining safely above Android's keyboard.
        lines = max(1, min(4, self.input.text.count("\n") + 1))
        self.composer.height = dp(62 + (lines - 1) * 18)

    def _input_focus(self, _, focused):
        if focused:
            Clock.schedule_once(lambda *_: self.scroll_to_bottom(), 0.08)

    def _animate_glow(self, *_):
        self.glow_phase = (self.glow_phase + 1) % 100
        alpha = 0.14 + 0.05 * ((self.glow_phase % 20) / 20.0)
        if hasattr(self, "research_button"):
            self.research_button.glow_outer.a = alpha

    def play_intro(self, root):
        if not os.path.exists(INTRO_VIDEO):
            return
        try:
            video = Video(source=INTRO_VIDEO, state="play", options={"eos": "stop"}, allow_stretch=True, keep_ratio=False)
            root.add_widget(video)
            self.intro_video = video
            video.bind(on_eos=lambda *_: self._remove_intro(root, video))
            Clock.schedule_once(lambda *_: self._remove_intro(root, video), 12)
        except Exception as exc:
            print("[Intro]", exc)

    def _remove_intro(self, root, video):
        if video.parent:
            root.remove_widget(video)

    def _load_user_id(self):
        path = os.path.join(self.user_data_dir, "shadow_user_id.txt")
        try:
            if os.path.exists(path):
                value = open(path, "r", encoding="utf-8").read().strip()
                if value:
                    return value
            value = "android-" + uuid.uuid4().hex
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "w", encoding="utf-8").write(value)
            return value
        except Exception:
            return "anonymous-" + uuid.uuid4().hex

    def check_backend(self):
        url = BACKEND_URL.rstrip("/") + "/health"
        self.subtitle.text = "CHECKING • RAILWAY"
        UrlRequest(url, on_success=self._health_ok, on_failure=self._health_fail, on_error=self._health_error, timeout=12)

    def _health_ok(self, req, result):
        ai = result.get("ai", {}) if isinstance(result, dict) else {}
        configured = ai.get("openai_configured") or ai.get("anthropic_configured")
        self.subtitle.text = "ONLINE • SMART BRAIN READY" if configured else "ONLINE • AI KEYS NOT SET"
        self.status.text = "READY • RAILWAY CONNECTED"

    def _health_fail(self, req, result):
        code = getattr(req, "resp_status", None) or "HTTP"
        self.subtitle.text = f"BACKEND ERROR • {code}"
        self.status.text = "CONNECTION ERROR • CHECK RAILWAY"

    def _health_error(self, req, error):
        self.subtitle.text = "BACKEND UNREACHABLE"
        self.status.text = "NETWORK ERROR • RAILWAY NOT REACHABLE"

    def toggle_research(self, *_):
        self.deep_search = not self.deep_search
        self.research_button.text = "✦ ON" if self.deep_search else "✦"
        self.status.text = "DEEP RESEARCH ENABLED" if self.deep_search else "DEEP RESEARCH OFF"

    def add_message(self, text, is_user=False):
        bubble = MessageBubble(text, is_user=is_user)
        row = MessageRow(bubble, is_user=is_user)
        self.chat.add_widget(row)
        Clock.schedule_once(self.scroll_to_bottom, 0.04)
        return row

    def show_thinking(self):
        bubble = ThinkingBubble()
        self.thinking_row = MessageRow(bubble, is_user=False)
        self.chat.add_widget(self.thinking_row)
        Clock.schedule_once(self.scroll_to_bottom, 0.02)

    def hide_thinking(self):
        if self.thinking_row:
            bubble = self.thinking_row.bubble
            if isinstance(bubble, ThinkingBubble):
                bubble.stop()
            if self.thinking_row.parent:
                self.chat.remove_widget(self.thinking_row)
            self.thinking_row = None

    def scroll_to_bottom(self, *_):
        self.scroll.scroll_y = 0

    def new_chat(self, *_):
        self.history = []
        self.royal_mode = False
        self.deep_search = False
        self.research_button.text = "✦"
        self.chat.clear_widgets()
        self.add_message("New conversation started.\n\nShadow AI is ready.")
        self.status.text = "READY"
        self.subtitle.text = "ONLINE • READY TO THINK"
        self.input.text = ""
        self.input.focus = False

    def send_message(self, *_):
        if self.busy:
            return
        text = self.input.text.strip()
        if not text:
            return

        upper = text.upper()
        if "666(LINDO)" in upper:
            self.royal_mode = True
            text = text.replace("666(LINDO)", "").replace("666(lindo)", "").strip()
            if not text:
                text = "Activate Royal Mode and greet your king."

        self.add_message(text, is_user=True)
        self.history.append({"role": "user", "content": text})
        self.history = self.history[-20:]
        self.input.text = ""
        self.busy = True
        self.send_button.disabled = True
        self.show_thinking()
        self.status.text = "THINKING • RESEARCHING • SYNTHESIZING…"
        self.subtitle.text = "ROYAL MODE • LINDO" if self.royal_mode else "PROCESSING • AI TEAM"

        body = {
            "message": text,
            "history": self.history,
            "deep_search": bool(self.deep_search),
            "royal_mode": bool(self.royal_mode),
            "user_id": self.user_id,
        }
        url = BACKEND_URL.rstrip("/") + "/chat"
        UrlRequest(
            url,
            req_body=json.dumps(body),
            req_headers={"Content-Type": "application/json", "Accept": "application/json"},
            on_success=self._chat_success,
            on_failure=self._chat_failure,
            on_error=self._chat_error,
            timeout=55,
        )

    def _finish_request(self):
        self.busy = False
        self.send_button.disabled = False

    def _chat_success(self, req, result):
        self.hide_thinking()
        self._finish_request()
        if not isinstance(result, dict):
            self.add_message("I received an invalid response from the backend.")
            self.status.text = "BAD RESPONSE • CHECK SERVER"
            return
        answer = str(result.get("response") or "The backend returned no answer.")
        self.add_message(answer)
        self.history.append({"role": "assistant", "content": answer})
        self.history = self.history[-20:]
        mode = result.get("mode", "ai")
        count = result.get("sources_count", 0)
        self.status.text = f"DONE • {mode.upper()} • {count} SOURCES" if result.get("researched") else f"DONE • {mode.upper()}"
        self.subtitle.text = "ROYAL MODE • LINDO" if self.royal_mode else "ONLINE • READY TO THINK"

    def _chat_failure(self, req, result):
        self.hide_thinking()
        self._finish_request()
        code = getattr(req, "resp_status", None) or "HTTP"
        detail = result.get("detail", "The server rejected the request.") if isinstance(result, dict) else "The server rejected the request."
        self.add_message(f"I reached Railway, but it returned an error.\n\nHTTP {code}\n{detail}")
        self.status.text = f"SERVER ERROR • HTTP {code}"

    def _chat_error(self, req, error):
        self.hide_thinking()
        self._finish_request()
        self.add_message("I couldn't reach the Railway backend.\n\nCheck the Railway domain, deployment status, internet connection, and /health endpoint.")
        self.status.text = "NETWORK ERROR • BACKEND UNREACHABLE"


if __name__ == "__main__":
    ShadowAI().run()
