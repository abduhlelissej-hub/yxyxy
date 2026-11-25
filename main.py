import array
import json
import math
import os
import tempfile
import urllib.parse
import urllib.request
import wave

from kivy.app import App
from kivy.clock import Clock
from kivy.core.audio import SoundLoader
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Line
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.textinput import TextInput
from kivy.utils import platform

CONFIG_FILE = "schutz_config.json"


def erzeuge_alarm_wav(ziel_pfad):
    if os.path.exists(ziel_pfad):
        return ziel_pfad
    sample_rate = 22050
    dauer = 0.6
    anzahl = int(sample_rate * dauer)
    daten = array.array("h")
    for i in range(anzahl):
        t = i / sample_rate
        freq = 880.0 if int(t * 8) % 2 == 0 else 587.33
        sample = int(16000 * math.sin(2.0 * math.pi * freq * t))
        daten.append(sample)
    with wave.open(ziel_pfad, "w") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(daten.tobytes())
    return ziel_pfad


def setze_stumm_modus(aktiv):
    if platform == "android":
        try:
            from jnius import autoclass

            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            Context = autoclass("android.content.Context")
            AudioManager = autoclass("android.media.AudioManager")

            activity = PythonActivity.mActivity
            am = activity.getSystemService(Context.AUDIO_SERVICE)
            if aktiv:
                am.setRingerMode(AudioManager.RINGER_MODE_SILENT)
                am.setStreamMute(AudioManager.STREAM_MUSIC, True)
            else:
                am.setRingerMode(AudioManager.RINGER_MODE_NORMAL)
                am.setStreamMute(AudioManager.STREAM_MUSIC, False)
            return True, "Android-Stummmodus aktualisiert"
        except Exception as exc:
            return False, f"Android-Audio-Hinweis: {exc}"
    return True, "Stummmodus aktiviert (Desktop-Simulation)" if aktiv else "Stummmodus aus (Desktop-Simulation)"


class AlarmLogoWidget(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(size_hint_y=None, height=130, **kwargs)
        self.bind(pos=self._redraw, size=self._redraw)

    def _redraw(self, *_args):
        self.canvas.clear()
        cx = self.x + self.width / 2
        cy = self.y + self.height / 2
        r = min(self.width, self.height) * 0.36
        with self.canvas:
            Color(0.95, 0.15, 0.15, 1)
            Ellipse(pos=(cx - r, cy - r), size=(r * 2, r * 2))
            Color(1, 1, 1, 1)
            Line(points=[cx, cy + r * 0.45, cx, cy - r * 0.1], width=4)
            Ellipse(pos=(cx - 4, cy - r * 0.45), size=(8, 8))


class SchutzApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.schutz_data_path = os.path.join(self.base_dir, CONFIG_FILE)
        self.schutz_data = self._lade_config()
        self.sound = None
        self.blink_ev = None
        self.blink_toggle = False
        self.schulmodus_an = False

    def _lade_config(self):
        if os.path.exists(self.schutz_data_path):
            try:
                with open(self.schutz_data_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception:
                pass
        return {"password": None}

    def _speichere_passwort(self, pw):
        self.schutz_data["password"] = pw
        with open(self.schutz_data_path, "w", encoding="utf-8") as f:
            json.dump(self.schutz_data, f, ensure_ascii=False)

    def _finde_eigenes_bild(self):
        for name in ("alarm.png", "alarm.jpg", "alarm.jpeg", "logo.png"):
            p = os.path.join(self.base_dir, name)
            if os.path.exists(p):
                return p
        return None

    def _finde_oder_erzeuge_sound(self):
        for name in ("alarm.mp3", "alarm.wav", "alarm.ogg"):
            p = os.path.join(self.base_dir, name)
            if os.path.exists(p):
                return p
        fallback_wav = os.path.join(tempfile.gettempdir(), "schutz_alarm_ton.wav")
        return erzeuge_alarm_wav(fallback_wav)

    def alarm_starten(self, status_label, alarm_box):
        status_label.text = "ALARM! FALSCHES PASSWORT!"
        alarm_box.clear_widgets()

        eigenes_bild = self._finde_eigenes_bild()
        if eigenes_bild:
            img = Image(source=eigenes_bild, allow_stretch=True, keep_ratio=True, size_hint_y=None, height=130)
            img.reload()
            alarm_box.add_widget(img)
        else:
            alarm_box.add_widget(AlarmLogoWidget())

        if self.sound is None:
            ton_pfad = self._finde_oder_erzeuge_sound()
            self.sound = SoundLoader.load(ton_pfad)
        if self.sound:
            self.sound.loop = True
            self.sound.stop()
            self.sound.play()

        if self.blink_ev is None:
            self.blink_ev = Clock.schedule_interval(self._blink_tick, 0.25)

    def _blink_tick(self, _dt):
        self.blink_toggle = not self.blink_toggle
        Window.clearcolor = (0.8, 0.06, 0.06, 1) if self.blink_toggle else (0.12, 0.12, 0.14, 1)

    def alarm_stoppen(self, alarm_box=None):
        if self.blink_ev is not None:
            self.blink_ev.cancel()
            self.blink_ev = None
        if self.sound is not None:
            self.sound.stop()
            self.sound.unload()
            self.sound = None
        Window.clearcolor = (0.12, 0.12, 0.16, 1)
        if alarm_box is not None:
            alarm_box.clear_widgets()

    def build(self):
        self.title = "Schutz"
        if platform != "android":
            Window.size = (412, 915)
        Window.clearcolor = (0.12, 0.12, 0.16, 1)
        self.sm = ScreenManager()

        hat_pw = bool(self.schutz_data.get("password"))

        lock_screen = Screen(name="lock")
        lock_layout = BoxLayout(orientation="vertical", padding=22, spacing=12)

        lock_layout.add_widget(Label(text="SCHUTZ", font_size="30sp", bold=True, size_hint_y=None, height=55))
        self.lock_hint = Label(
            text="Eigenes Passwort festlegen:" if not hat_pw else "Passwort eingeben:",
            font_size="20sp",
            size_hint_y=None,
            height=40,
        )
        lock_layout.add_widget(self.lock_hint)

        self.pw_field = TextInput(
            hint_text="Neues Passwort..." if not hat_pw else "Dein Passwort...",
            password=True,
            multiline=False,
            font_size="22sp",
            size_hint_y=None,
            height=58,
        )
        lock_layout.add_widget(self.pw_field)

        self.alarm_box = BoxLayout(orientation="vertical", size_hint_y=None, height=135)
        lock_layout.add_widget(self.alarm_box)

        action_btn = Button(
            text="Passwort speichern" if not hat_pw else "Entsperren",
            font_size="20sp",
            size_hint_y=None,
            height=60,
        )

        def on_lock_submit(*_args):
            eingabe = self.pw_field.text.strip()
            gespeichert = self.schutz_data.get("password")
            if not gespeichert:
                if len(eingabe) < 2:
                    self.lock_hint.text = "Bitte mindestens 2 Zeichen eingeben!"
                    return
                self._speichere_passwort(eingabe)
                self.pw_field.text = ""
                self.pw_field.hint_text = "Dein Passwort..."
                self.lock_hint.text = "Passwort gespeichert! Jetzt einloggen:"
                action_btn.text = "Entsperren"
            else:
                if eingabe == gespeichert:
                    self.alarm_stoppen(self.alarm_box)
                    self.pw_field.text = ""
                    self.lock_hint.text = "Passwort eingeben:"
                    self.sm.current = "hub"
                else:
                    self.alarm_starten(self.lock_hint, self.alarm_box)

        self.pw_field.bind(on_text_validate=on_lock_submit)
        action_btn.bind(on_press=on_lock_submit)
        lock_layout.add_widget(action_btn)

        lock_screen.add_widget(lock_layout)
        self.sm.add_widget(lock_screen)

        hub_screen = Screen(name="hub")
        hub_layout = BoxLayout(orientation="vertical", padding=22, spacing=14)
        hub_layout.add_widget(Label(text="SCHUTZ - MENÜ", font_size="28sp", bold=True, size_hint_y=None, height=55))

        self.schul_status = Label(
            text="Schulmodus: AUS",
            font_size="20sp",
            size_hint_y=None,
            height=45,
        )
        hub_layout.add_widget(self.schul_status)

        schul_btn = Button(
            text="Schulmodus AN / AUS (Stumm)",
            font_size="20sp",
            size_hint_y=None,
            height=65,
        )

        def toggle_schulmodus(*_args):
            self.schulmodus_an = not self.schulmodus_an
            _ok, info = setze_stumm_modus(self.schulmodus_an)
            if self.schulmodus_an:
                Window.clearcolor = (0.1, 0.25, 0.45, 1)
                self.schul_status.text = f"Schulmodus: AN | {info}"
            else:
                Window.clearcolor = (0.12, 0.12, 0.16, 1)
                self.schul_status.text = f"Schulmodus: AUS | {info}"

        schul_btn.bind(on_press=toggle_schulmodus)
        hub_layout.add_widget(schul_btn)

        browser_btn = Button(
            text="Secret Browser öffnen (ohne Verlauf)",
            font_size="20sp",
            size_hint_y=None,
            height=65,
        )
        browser_btn.bind(on_press=lambda *_: setattr(self.sm, "current", "browser"))
        hub_layout.add_widget(browser_btn)

        lock_again_btn = Button(
            text="Sperren / Passwort ändern",
            font_size="18sp",
            size_hint_y=None,
            height=55,
        )

        def sperren_und_reset(*_args):
            self.alarm_stoppen(self.alarm_box)
            self.lock_hint.text = "Passwort eingeben:"
            self.sm.current = "lock"

        lock_again_btn.bind(on_press=sperren_und_reset)
        hub_layout.add_widget(lock_again_btn)

        reset_pw_btn = Button(
            text="Gespeichertes Passwort löschen",
            font_size="16sp",
            size_hint_y=None,
            height=50,
        )

        def loesche_pw(*_args):
            self._speichere_passwort(None)
            action_btn.text = "Passwort speichern"
            self.pw_field.hint_text = "Neues Passwort..."
            self.lock_hint.text = "Eigenes Passwort festlegen:"
            self.sm.current = "lock"

        reset_pw_btn.bind(on_press=loesche_pw)
        hub_layout.add_widget(reset_pw_btn)

        hub_screen.add_widget(hub_layout)
        self.sm.add_widget(hub_screen)

        browser_screen = Screen(name="browser")
        b_layout = BoxLayout(orientation="vertical", padding=16, spacing=10)
        b_layout.add_widget(
            Label(
                text="SECRET BROWSER (KEIN VERLAUF)",
                font_size="22sp",
                bold=True,
                size_hint_y=None,
                height=45,
            )
        )

        url_input = TextInput(
            text="https://duckduckgo.com",
            hint_text="URL oder Suchbegriff...",
            multiline=False,
            font_size="18sp",
            size_hint_y=None,
            height=52,
        )
        b_layout.add_widget








