import json
import os
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.uix.filechooser import FileChooserIconView
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.core.audio import SoundLoader

RICHTIGES_PASSWORT = "1234"
CONFIG_DATEI = "einstellungen.json"


class PasswortApp(App):
    def build(self):
        self.fehlversuche = 0
        self.config = self.lade_einstellungen()

        self.layout = BoxLayout(orientation="vertical", padding=20, spacing=12)

        self.info = Label(text="Passwort eingeben:", font_size="22sp", size_hint_y=None, height=50)
        self.eingabe = TextInput(password=True, multiline=False, font_size="22sp", size_hint_y=None, height=60)
        self.pruef_btn = Button(text="Prüfen", font_size="20sp", size_hint_y=None, height=70)
        self.pruef_btn.bind(on_press=self.pruefe_passwort)

        auswahl_leiste = BoxLayout(orientation="horizontal", spacing=10, size_hint_y=None, height=60)
        self.bild_btn = Button(text="Bild wählen", font_size="16sp")
        self.bild_btn.bind(on_press=lambda x: self.oeffne_dateiauswahl("bild", ["*.png", "*.jpg", "*.jpeg"]))

        self.sound_btn = Button(text="Sound wählen", font_size="16sp")
        self.sound_btn.bind(on_press=lambda x: self.oeffne_dateiauswahl("sound", ["*.mp3", "*.wav", "*.ogg"]))

        auswahl_leiste.add_widget(self.bild_btn)
        auswahl_leiste.add_widget(self.sound_btn)

        self.status_auswahl = Label(
            text=f"Bild: {os.path.basename(self.config['bild']) or 'keins'} | Sound: {os.path.basename(self.config['sound']) or 'keiner'}",
            font_size="14sp",
            size_hint_y=None,
            height=35,
        )

        self.bild_widget = Image(source=self.config["bild"], opacity=0)
        self.sound = SoundLoader.load(self.config["sound"]) if self.config["sound"] else None

        self.layout.add_widget(self.info)
        self.layout.add_widget(self.eingabe)
        self.layout.add_widget(self.pruef_btn)
        self.layout.add_widget(auswahl_leiste)
        self.layout.add_widget(self.status_auswahl)
        self.layout.add_widget(self.bild_widget)
        return self.layout

    def lade_einstellungen(self):
        standard = {"bild": "warnung.png", "sound": "alarm.mp3"}
        if os.path.exists(CONFIG_DATEI):
            try:
                with open(CONFIG_DATEI, "r", encoding="utf-8") as f:
                    daten = json.load(f)
                    standard.update(daten)
            except Exception:
                pass
        return standard

    def speichere_einstellungen(self):
        with open(CONFIG_DATEI, "w", encoding="utf-8") as f:
            json.dump(self.config, f)

    def oeffne_dateiauswahl(self, typ, filter_liste):
        chooser = FileChooserIconView(filters=filter_liste)
        popup = Popup(title=f"{typ.capitalize()} auswählen", content=chooser, size_hint=(0.9, 0.8))

        def ausgewaehlt(instance, selection):
            if selection:
                pfad = selection[0]
                if typ == "bild":
                    self.config["bild"] = pfad
                    self.bild_widget.source = pfad
                    self.bild_widget.reload()
                elif typ == "sound":
                    self.config["sound"] = pfad
                    self.sound = SoundLoader.load(pfad)

                self.speichere_einstellungen()
                self.status_auswahl.text = (
                    f"Bild: {os.path.basename(self.config['bild']) or 'keins'} | "
                    f"Sound: {os.path.basename(self.config['sound']) or 'keiner'}"
                )
                popup.dismiss()

        chooser.bind(selection=ausgewaehlt)
        popup.open()

    def pruefe_passwort(self, instance):
        if self.eingabe.text == RICHTIGES_PASSWORT:
            self.fehlversuche = 0
            self.bild_widget.opacity = 0
            self.info.text = "Zugang erlaubt!"
        else:
            self.fehlversuche += 1
            if self.fehlversuche >= 2:
                self.info.text = "2x falsch! Alarm!"
                self.bild_widget.opacity = 1
                if self.sound:
                    self.sound.stop()
                    self.sound.play()
                self.fehlversuche = 0
            else:
                self.info.text = "1x falsch – noch 1 Versuch!"
        self.eingabe.text = ""


if __name__ == "__main__":
    PasswortApp().run()
