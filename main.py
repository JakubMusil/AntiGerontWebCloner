Jasně, omlouvám se za nedorozumění – vrátím původní wget2 a přidám lepší logování, abychom měli přehled o tom, co se při stahování děje. Upravím kód tak, aby:

Zachoval původní příkaz wget2 (bez -k a dalších změn, pokud chceš přesně tvou verzi).
Přidal detailní logování výstupu stdout a stderr od wget2 v reálném čase.
Nahradil obecný výběr složky dropdownem pro složky v mirror_output.
Použiji subprocess s živým čtením výstupu, aby se logy zobrazovaly průběžně, a ne až po dokončení.

Upravený kód main.py
python
Wrap
Copy
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.textfield import MDTextField
from kivymd.uix.button import MDRaisedButton, MDFlatButton
from kivymd.uix.progressbar import MDProgressBar
from kivymd.uix.label import MDLabel
from kivymd.uix.dialog import MDDialog
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.dropdownitem import MDDropDownItem
from kivymd.uix.menu import MDDropdownMenu
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock
import subprocess
import os
import threading
import re
import queue

class MirrorApp(MDApp):
    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "DeepOrange"
        self.theme_cls.accent_palette = "Gray"

        screen = MDScreen()
        layout = MDBoxLayout(orientation="vertical", padding=20, spacing=20)

        self.url_input = MDTextField(
            hint_text="Zadej URL webu",
            helper_text="Např. https://example.com",
            mode="rectangle",
            icon_right="web",
            size_hint=(1, None),
            height="50dp"
        )

        self.depth_input = MDTextField(
            hint_text="Maximální hloubka (1-5)",
            helper_text="Počet úrovní odkazů",
            mode="rectangle",
            input_filter="int",
            text="1",
            size_hint=(1, None),
            height="50dp"
        )

        self.replacements_input = MDTextField(
            hint_text="Cesta k souboru replacements.txt",
            helper_text="Např. ./replacements.txt",
            mode="rectangle",
            icon_right="file-document",
            text="replacements.txt",
            size_hint=(1, None),
            height="50dp"
        )

        # Dropdown pro výběr složky z mirror_output
        self.folder_dropdown = MDDropDownItem(
            text="Vyber složku z mirror_output",
            size_hint=(1, None),
            height="50dp"
        )
        self.folder_dropdown.bind(on_release=self.open_folder_menu)

        self.progress = MDProgressBar(
            value=0,
            size_hint=(1, None),
            height="20dp"
        )

        self.log = MDLabel(
            text="Připraveno",
            halign="left",
            valign="top",
            size_hint=(1, 1),
            text_size=(None, None)
        )
        scroll = ScrollView()
        scroll.add_widget(self.log)

        button_layout = MDBoxLayout(orientation="horizontal", spacing=10, padding=[0, 10, 0, 0])
        self.start_button = MDRaisedButton(
            text="Spustit zrcadlení",
            pos_hint={"center_x": 0.5},
            on_release=self.start_mirroring
        )
        self.stop_button = MDRaisedButton(
            text="Zastavit",
            pos_hint={"center_x": 0.5},
            disabled=True,
            on_release=self.stop_mirroring
        )
        self.replace_button = MDRaisedButton(
            text="Nahradit text",
            pos_hint={"center_x": 0.5},
            on_release=self.replace_text
        )
        button_layout.add_widget(self.start_button)
        button_layout.add_widget(self.stop_button)
        button_layout.add_widget(self.replace_button)

        layout.add_widget(self.url_input)
        layout.add_widget(self.depth_input)
        layout.add_widget(self.replacements_input)
        layout.add_widget(self.folder_dropdown)
        layout.add_widget(self.progress)
        layout.add_widget(scroll)
        layout.add_widget(button_layout)
        screen.add_widget(layout)

        self.running = False
        self.output_dir = "mirror_output"
        self.selected_folder = self.output_dir  # Výchozí složka
        self.log_queue = queue.Queue()  # Fronta pro logování

        return screen

    def update_log(self, message):
        """Aktualizuje logovací okno."""
        self.log.text += f"\n{message}"
        self.root.children[0].children[1].scroll_y = 0

    def open_folder_menu(self, instance):
        """Otevře dropdown menu se složkami z mirror_output."""
        if not os.path.exists(self.output_dir):
            self.show_error("Nejprve proveď zrcadlení, aby byly k dispozici složky!")
            return

        folders = [self.output_dir] + [os.path.join(self.output_dir, d) for d in os.listdir(self.output_dir) if os.path.isdir(os.path.join(self.output_dir, d))]
        menu_items = [{"text": os.path.basename(f) or "root", "viewclass": "OneLineListItem", "on_release": lambda x=f: self.set_folder(x)} for f in folders]
        self.folder_menu = MDDropdownMenu(caller=instance, items=menu_items, width_mult=4)
        self.folder_menu.open()

    def set_folder(self, folder_path):
        """Nastaví vybranou složku."""
        self.selected_folder = folder_path
        self.folder_dropdown.text = os.path.basename(folder_path) or "root"
        self.folder_menu.dismiss()

    def start_mirroring(self, instance):
        url = self.url_input.text.strip()
        depth = int(self.depth_input.text or 1)

        if not url.startswith("http"):
            self.show_error("Zadej platnou URL začínající na http/https!")
            return

        self.running = True
        self.start_button.disabled = True
        self.stop_button.disabled = False
        self.replace_button.disabled = True
        self.progress.value = 0
        self.update_log(f"Spouštím zrcadlení: {url}")

        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

        threading.Thread(target=self.mirror_site, args=(url, depth)).start()
        Clock.schedule_interval(self.update_progress, 0.5)
        Clock.schedule_interval(self.process_log_queue, 0.1)  # Průběžné logování

    def stop_mirroring(self, instance):
        self.running = False
        if hasattr(self, "process") and self.process:
            self.process.terminate()
        self.start_button.disabled = False
        self.stop_button.disabled = True
        self.replace_button.disabled = False
        self.update_log("Zrcadlení zastaveno uživatelem.")
        Clock.unschedule(self.process_log_queue)

    def mirror_site(self, url, max_depth):
        """Spustí wget2 pro zrcadlení webu s detailním logováním."""
        try:
            cmd = [
                "wget2",
                "--mirror",
                f"--level={max_depth}",
                "--convert-links",
                "--adjust-extension",
                "--page-requisites",
                f"--directory-prefix={self.output_dir}",
                url
            ]
            self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, universal_newlines=True)
            
            # Čtení výstupu v reálném čase
            while self.running and self.process.poll() is None:
                stdout_line = self.process.stdout.readline()
                stderr_line = self.process.stderr.readline()
                if stdout_line:
                    self.log_queue.put(f"[wget2] {stdout_line.strip()}")
                if stderr_line:
                    self.log_queue.put(f"[wget2 ERROR] {stderr_line.strip()}")

            # Dokončení procesu
            stdout, stderr = self.process.communicate()
            if stdout:
                for line in stdout.splitlines():
                    self.log_queue.put(f"[wget2] {line.strip()}")
            if stderr:
                for line in stderr.splitlines():
                    self.log_queue.put(f"[wget2 ERROR] {line.strip()}")

            if self.running:
                if self.process.returncode == 0:
                    self.update_log("Zrcadlení dokončeno!")
                else:
                    self.update_log(f"Chyba při zrcadlení, kód: {self.process.returncode}")
            self.running = False
            self.start_button.disabled = False
            self.stop_button.disabled = True
            self.replace_button.disabled = False

        except FileNotFoundError:
            self.update_log("Chyba: wget2 není nainstalován na tvém systému!")
            self.running = False
            self.start_button.disabled = False
            self.stop_button.disabled = True
            self.replace_button.disabled = False
        except Exception as e:
            self.update_log(f"Chyba: {str(e)}")
            self.running = False
            self.start_button.disabled = False
            self.stop_button.disabled = True
            self.replace_button.disabled = False

    def process_log_queue(self, dt):
        """Zpracovává frontu logů a aktualizuje GUI."""
        while not self.log_queue.empty():
            message = self.log_queue.get()
            self.update_log(message)

    def replace_text(self, instance):
        replacements_file = self.replacements_input.text.strip()
        target_folder = self.selected_folder

        if not os.path.exists(replacements_file):
            self.show_error(f"Soubor {replacements_file} nebyl nalezen!")
            return

        if not os.path.exists(target_folder):
            self.show_error(f"Složka {target_folder} nebyla nalezena!")
            return

        replacements = {}
        try:
            with open(replacements_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and "|||" in line:
                        search_text, replace_text = line.split("|||", 1)
                        replacements[search_text] = replace_text
            if not replacements:
                self.show_error("Soubor je prázdný nebo neobsahuje platná pravidla ve formátu 'hledaný_text|||nahrazující_text'!")
                return
        except Exception as e:
            self.show_error(f"Chyba při čtení souboru: {str(e)}")
            return

        self.update_log(f"Spouštím nahrazování textů ve složce: {target_folder}")
        total_replaced = 0

        for root, _, files in os.walk(target_folder):
            for file in files:
                if file.endswith((".html", ".htm", ".css", ".js")):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            content = f.read()
                        original_content = content
                        for search_text, replace_text in replacements.items():
                            content, count = re.subn(re.escape(search_text), replace_text, content)
                            total_replaced += count
                        if content != original_content:
                            with open(file_path, "w", encoding="utf-8") as f:
                                f.write(content)
                            self.update_log(f"Upraven soubor: {file_path}")
                    except Exception as e:
                        self.update_log(f"Chyba při zpracování {file_path}: {str(e)}")

        self.update_log(f"Celkem nahrazeno: {total_replaced} výskytů.")

    def update_progress(self, dt):
        if self.running:
            if self.progress.value < 90:
                self.progress.value += 5
        else:
            self.progress.value = 100
            Clock.unschedule(self.update_progress)

    def show_error(self, message):
        dialog = MDDialog(
            title="Chyba",
            text=message,
            buttons=[MDFlatButton(text="OK", on_release=lambda x: dialog.dismiss())]
        )
        dialog.open()

if __name__ == "__main__":
    MirrorApp().run()
