import os
import sys
import subprocess
import configparser
import customtkinter as ctk
import json
import threading
import urllib.request
import zipfile
import io
from PIL import Image, ImageFilter, ImageEnhance, ImageDraw
from translations import TRANSLATIONS, LANGUAGES_LIST

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class EldenRingLauncher(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Elden Ring Launcher")
        self.attributes("-alpha", 0.0) # Start fully transparent to prevent flash
        self.resizable(False, False)

        # Determine base directory
        if getattr(sys, 'frozen', False):
            self.launcher_base = os.path.dirname(sys.executable)
        else:
            self.launcher_base = os.path.dirname(os.path.abspath(__file__))

        # Config Path Migration Logic
        old_config_path = os.path.join(self.launcher_base, "launcher_config.ini")
        appdata_dir = os.getenv('APPDATA')
        if not appdata_dir: # Fallback for non-Windows if any
            appdata_dir = os.path.expanduser("~")
        
        self.config_dir = os.path.join(appdata_dir, "ERLauncher")
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)
            
        self.config_path = os.path.join(self.config_dir, "launcher_config.ini")
        
        # Migrate existing local config if global one doesn't exist yet
        if os.path.exists(old_config_path) and not os.path.exists(self.config_path):
            try:
                import shutil
                shutil.move(old_config_path, self.config_path)
                print(f"Migrated config from {old_config_path} to {self.config_path}")
            except Exception as e:
                print(f"Failed to migrate config: {e}")
        
        self.found_paths_set = set()
        self.bootstrap_debug_log = []
        self.modpack_var = ctk.StringVar(value="Vanilla")
        
        # Language Setup
        saved_lang = self.read_config_value("language", "en")
        self.lang_var = ctk.StringVar(value=saved_lang)
        
        self.scroll_frame = None
        
        # Center the window
        self.center_window(600, 550)
        
        # Set Window Icon
        self.icon_path = resource_path("app_icon.ico")
        if os.path.exists(self.icon_path):
            self.after(200, lambda: self.iconbitmap(self.icon_path))
        
        # Set theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.game_dir = None
        self.load_config()

        # UI Setup (Base)
        self.setup_ui()

    def center_window(self, width, height):
        self.update_idletasks()
        # Get screen dimensions
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        # Calculate x and y coordinates
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        
        # Ensure it's on screen even if something went wrong
        if x < 0: x = 0
        if y < 0: y = 0
        
        self.geometry(f'{width}x{height}+{x}+{y}')
        self.lift()      # Bring to front
        self.focus_force() # Force focus

    def load_config(self):
        self.launcher_config = configparser.ConfigParser()
        if os.path.exists(self.config_path):
            self.launcher_config.read(self.config_path)
            path = self.launcher_config.get('Main', 'game_path', fallback=None)
            if path and os.path.exists(path):
                self.game_dir = path
        
        if self.game_dir:
            self.update_paths(self.game_dir)

    def save_config(self, path):
        if not self.launcher_config.has_section('Main'):
            self.launcher_config.add_section('Main')
        self.launcher_config.set('Main', 'game_path', path)
        with open(self.config_path, 'w') as f:
            self.launcher_config.write(f)
        self.game_dir = path
        self.update_paths(path)

    def update_paths(self, game_dir):
        self.settings_path = os.path.join(game_dir, "ersc_settings.ini")
        self.launch_exe = os.path.join(game_dir, "EldenRing_Launcher.exe")
        self.real_exe = os.path.join(game_dir, "eldenring.exe")

    def _t(self, key):
        lang = self.lang_var.get()
        # Fallback to English if key missing in translation
        return TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, TRANSLATIONS["en"].get(key, key))

    def on_lang_change(self, value):
        # Find code from display name
        lang_code = "en"
        for code, name in LANGUAGES_LIST:
            if name == value:
                lang_code = code
                break
        
        self.lang_var.set(lang_code)
        self.save_config_value("language", lang_code)
        self.setup_ui() # Refresh UI

    def setup_ui(self):
        # Clear existing widgets if any (for re-init)
        for widget in self.winfo_children():
            widget.destroy()

        # Background Image
        self.bg_image_path = resource_path("background.png")
        if os.path.exists(self.bg_image_path):
            bg_pil = Image.open(self.bg_image_path)
            self.bg_image = ctk.CTkImage(light_image=bg_pil, dark_image=bg_pil, size=(600, 550))
            self.bg_label = ctk.CTkLabel(self, image=self.bg_image, text="")
            self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)

        # Create central overlay
        self.overlay = ctk.CTkFrame(self, fg_color="#151515", bg_color="transparent", corner_radius=15,
                                    border_width=1, border_color="#d4af37")
        self.overlay.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.85, relheight=0.9)

        if not self.game_dir:
            self.show_setup_view()
        else:
            self.show_main_view()
            
        # Language Selector outside the frames
        self.add_language_selector(self)
            
        # Ensure window is visible and fades in
        self.update() # Force update to map window
        self.fade_in()

    def show_setup_view(self):
        # Clear overlay for setup
        for widget in self.overlay.winfo_children():
            widget.destroy()
        
        ctk.CTkLabel(self.overlay, text=self._t("setup_title"), font=("Cinzel", 24, "bold"), text_color="#d4af37").pack(pady=(30, 10))
        ctk.CTkLabel(self.overlay, text=self._t("setup_desc"), 
                      font=("Arial", 13), text_color="#aaaaaa").pack(pady=10)
        
        self.search_btn = ctk.CTkButton(self.overlay, text=self._t("auto_discover"), command=self.start_auto_discovery,
                                         fg_color="#3e4a3d", hover_color="#4e5b4d", border_width=1, border_color="#d4af37")
        self.search_btn.pack(pady=20)
        
        ctk.CTkButton(self.overlay, text=self._t("browse_manual"), command=self.manual_browse,
                       fg_color="#1a1a1a", hover_color="#2a2a2a", border_width=1, border_color="#d4af37").pack(pady=5)
        
        self.setup_status = ctk.CTkLabel(self.overlay, text="", font=("Arial", 11), text_color="gray")
        self.setup_status.pack(pady=10)

    def start_auto_discovery(self):
        self.found_paths_set.clear()
        self.search_btn.configure(state="disabled", text=self._t("searching"))
        threading.Thread(target=self.run_discovery, daemon=True).start()

    def run_discovery(self):
        # 1. Check Registry (Steam)
        self.update_setup_status(self._t("searching"))
        try:
            import winreg
            steam_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App 1245620")
            install_path, _ = winreg.QueryValueEx(steam_key, "InstallLocation")
            game_path = os.path.join(install_path, "Game")
            if os.path.exists(os.path.join(game_path, "eldenring.exe")):
                self.after(0, lambda: self.handle_single_path_found(game_path))
        except:
            pass

        # 2. Check Steam Library Folders
        self.update_setup_status(self._t("searching"))
        for p in self.find_in_steam_libraries():
            self.after(0, lambda path=p: self.handle_single_path_found(path))

        # 3. Fast scan of drives (Common paths)
        drives = [f"{d}:\\" for d in "CDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.exists(f"{d}:\\")]
        for drive in drives:
            self.update_setup_status(f"{self._t('searching')} ({drive})...")
            common = [
                os.path.join(drive, "Program Files (x86)", "Steam", "steamapps", "common", "ELDEN RING", "Game"),
                os.path.join(drive, "SteamLibrary", "steamapps", "common", "ELDEN RING", "Game"),
                os.path.join(drive, "Games", "ELDEN RING", "Game")
            ]
            for c in common:
                if os.path.exists(os.path.join(c, "eldenring.exe")):
                    self.after(0, lambda path=c: self.handle_single_path_found(path))
        
        # 4. Deep scan fallback (Always do it to be thorough, per user request)
        for drive in drives:
            self.update_setup_status(f"{self._t('searching')} ({drive})...")
            for root, dirs, files in os.walk(drive):
                if any(x in root.lower() for x in ["windows", "programdata", "system32"]):
                    continue
                
                # Show deep scan progress
                if len(files) % 10 == 0: # Throttled UI update
                    self.update_setup_status(f"Scanning: {root[:40]}...")

                if "eldenring.exe" in files:
                    # Removed the strict check for "EldenRing_Launcher.exe"
                    self.after(0, lambda path=root: self.handle_single_path_found(path))

        self.update_setup_status(self._t("search_complete"))
        self.after(0, self.check_discovery_end)

    def check_discovery_end(self):
        if not self.found_paths_set:
            self.search_btn.configure(state="normal", text=self._t("auto_discover"))
            self.setup_status.configure(text=self._t("no_install_found"), text_color="#ff4444")
        else:
            self.setup_status.configure(text=f"{self._t('found_instances')} {len(self.found_paths_set)}", text_color="#d4af37")

    def handle_single_path_found(self, path):
        if path not in self.found_paths_set:
            self.found_paths_set.add(path)
            if len(self.found_paths_set) == 1:
                self.init_selection_ui()
            self.add_path_to_selection_list(path)

    def init_selection_ui(self):
        for widget in self.overlay.winfo_children():
            widget.destroy()
            
        ctk.CTkLabel(self.overlay, text=self._t("verify_install"), font=("Cinzel", 20, "bold"), text_color="#d4af37").pack(pady=(20, 5))
        ctk.CTkLabel(self.overlay, text=self._t("found_instances"), 
                      font=("Arial", 11), text_color="#aaaaaa").pack(pady=5)
        
        self.scroll_frame = ctk.CTkScrollableFrame(self.overlay, fg_color="transparent", border_width=1, border_color="#333333")
        self.scroll_frame.pack(pady=10, padx=20, fill="both", expand=True)
        
        self.setup_status = ctk.CTkLabel(self.overlay, text=self._t("searching_more"), font=("Arial", 11), text_color="gray")
        self.setup_status.pack(pady=5)
        
        ctk.CTkButton(self.overlay, text=self._t("back_retry_btn"), command=self.setup_ui).pack(pady=5)

    def add_path_to_selection_list(self, path):
        if self.scroll_frame:
            btn = ctk.CTkButton(self.scroll_frame, text=path, anchor="w", fg_color="#1a1a1a", hover_color="#333333",
                                 command=lambda p=path: self.complete_setup(p))
            btn.pack(pady=2, fill="x")

    def find_in_steam_libraries(self):
        paths = []
        try:
            import winreg
            hkey = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
            steam_path, _ = winreg.QueryValueEx(hkey, "SteamPath")
            vdf_path = os.path.join(steam_path.replace("/", "\\"), "steamapps", "libraryfolders.vdf")
            if os.path.exists(vdf_path):
                with open(vdf_path, 'r') as f:
                    content = f.read()
                    import re
                    # Simple regex to find "path" "..."
                    matches = re.findall(r'"path"\s+"([^"]+)"', content)
                    for m in matches:
                        p = os.path.join(m.replace("\\\\", "\\"), "steamapps", "common", "ELDEN RING", "Game")
                        if os.path.exists(os.path.join(p, "eldenring.exe")):
                            paths.append(p)
        except:
            pass
        return paths

    def update_setup_status(self, text):
        if hasattr(self, 'setup_status') and self.setup_status.winfo_exists():
            self.after(0, lambda: self.setup_status.configure(text=text))

    def update_status(self, text, color="gray"):
        if hasattr(self, 'status_label') and self.status_label.winfo_exists():
            self.after(0, lambda: self.status_label.configure(text=text, text_color=color))

    def manual_browse(self):
        from tkinter import filedialog
        path = filedialog.askdirectory(title=self._t("setup_title"))
        if path:
            if os.path.exists(os.path.join(path, "eldenring.exe")):
                self.complete_setup(path)
            else:
                self.setup_status.configure(text=self._t("invalid_folder"), text_color="#ff4444")

    def complete_setup(self, path):
        # 1. Standardize folder name to "Game" (case-insensitive check)
        folder_name = os.path.basename(path)
        if folder_name.lower() != "game":
            parent_dir = os.path.dirname(path)
            new_path = os.path.join(parent_dir, "Game")
            
            try:
                # If "Game" already exists, we might have a conflict. 
                if os.path.exists(new_path) and path.lower() != new_path.lower():
                    # If it already exists, we can't rename simply.
                    self.show_rename_error(path, new_path, self._t("rename_conflict"))
                    return
                
                os.rename(path, new_path)
                path = new_path
                print(f"Standardized folder name to 'Game': {path}")
            except Exception as e:
                self.show_rename_error(path, new_path, str(e))
                return

        # 2. Check if launcher needs bootstrapping
        if not os.path.exists(os.path.join(path, "EldenRing_Launcher.exe")):
            self.show_bootstrap_ui(path)
        else:
            self.save_config(path)
            self.setup_ui()

    def show_rename_error(self, old_path, new_path, error_detail):
        # Clear overlay
        for widget in self.overlay.winfo_children():
            widget.destroy()
            
        ctk.CTkLabel(self.overlay, text=self._t("rename_failed"), font=("Cinzel", 22, "bold"), text_color="#ff4444").pack(pady=(30, 10))
        
        err_box = ctk.CTkTextbox(self.overlay, width=500, height=120, fg_color="#1a1a1a", text_color="#ff6666", font=("Consolas", 12))
        err_box.pack(pady=10, padx=20)
        err_box.insert("0.0", f"{self._t('error_prefix')} {error_detail}\n\nTarget: {new_path}")
        err_box.configure(state="disabled")
        
        ctk.CTkLabel(self.overlay, text=self._t("common_solutions"), font=("Arial", 13, "bold"), text_color="#d4af37").pack(pady=(10, 5))
        
        # Note: Tips are slightly complex to translate individually, keeping them for now or using generic ones if needed
        # For 50 languages, generic tips or localized ones are better. I'll use translated keys if I add them.
        tips = [
            self._t("tip_1"),
            self._t("tip_2"),
            self._t("tip_3"),
            self._t("tip_4"),
            self._t("tip_5")
        ]
        
        tips_text = "\n".join(tips)
        ctk.CTkLabel(self.overlay, text=tips_text, font=("Arial", 12), text_color="#aaaaaa", justify="left").pack(pady=5)
        
        btn_frame = ctk.CTkFrame(self.overlay, fg_color="transparent")
        btn_frame.pack(pady=20)
        
        ctk.CTkButton(btn_frame, text=self._t("retry_rename"), command=lambda: self.complete_setup(old_path),
                       fg_color="#3e4a3d", hover_color="#4e5b4d", width=150).pack(side="left", padx=10)
                       
        ctk.CTkButton(btn_frame, text=self._t("back_to_selection"), command=self.show_setup_view,
                       fg_color="#333333", hover_color="#444444", width=150).pack(side="left", padx=10)

    def show_bootstrap_ui(self, path):
        # Clear overlay for bootstrap
        for widget in self.overlay.winfo_children():
            widget.destroy()
            
        ctk.CTkLabel(self.overlay, text=self._t("bootstrapping"), font=("Cinzel", 24, "bold"), text_color="#d4af37").pack(pady=(30, 10))
        self.bootstrap_label = ctk.CTkLabel(self.overlay, text=self._t("missing_files"), 
                                             font=("Arial", 13), text_color="#aaaaaa")
        self.bootstrap_label.pack(pady=10)
        
        self.progress_bar = ctk.CTkProgressBar(self.overlay, width=300, progress_color="#d4af37")
        self.progress_bar.pack(pady=20)
        self.progress_bar.set(0)
        
        # Always show a small debug button at the bottom during bootstrap
        self.debug_btn = ctk.CTkButton(self.overlay, text=self._t("debug_info_btn"), command=self.show_debug_log, 
                                        width=100, height=20, font=("Arial", 10),
                                        fg_color="#333333", hover_color="#444444")
        self.debug_btn.pack(pady=5)
        
        threading.Thread(target=self.run_bootstrap, args=(path,), daemon=True).start()

    def run_bootstrap(self, path):
        url = "https://github.com/conan513/er_launcher/releases/download/v1/spp_er.zip"
        temp_zip = os.path.join(path, "spp_er_temp.zip")
        self.bootstrap_debug_log = [f"Target URL: {url}", f"Target Path: {path}"]
        
        try:
            self.update_bootstrap_status(self._t("downloading"))
            self.after(0, lambda: self.progress_bar.set(0.1))
            
            # 1. Try CURL
            download_success = False
            ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            try:
                self.bootstrap_debug_log.append("Attempt 1: curl...")
                cmd = f'curl -L -k -A "{ua}" -o "{temp_zip}" "{url}"'
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                if result.returncode == 0 and self.validate_zip(temp_zip):
                    download_success = True
                else:
                    self.bootstrap_debug_log.append(f"curl failed. ReturnCode: {result.returncode}")
                    if result.stderr: self.bootstrap_debug_log.append(f"curl stderr: {result.stderr[:200]}")
            except Exception as e:
                self.bootstrap_debug_log.append(f"curl Exception: {str(e)}")

            # 2. Try PowerShell BITS
            if not download_success:
                try:
                    self.update_bootstrap_status(self._t("retry_bits"))
                    self.after(0, lambda: self.progress_bar.set(0.3))
                    self.bootstrap_debug_log.append("Attempt 2: Start-BitsTransfer...")
                    if os.path.exists(temp_zip): os.remove(temp_zip)
                    ps_cmd = f"powershell -Command \"Start-BitsTransfer -Source '{url}' -Destination '{temp_zip}'\""
                    result = subprocess.run(ps_cmd, shell=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                    if result.returncode == 0 and self.validate_zip(temp_zip):
                        download_success = True
                    else:
                        self.bootstrap_debug_log.append(f"BITS failed. ReturnCode: {result.returncode}")
                        if result.stderr: self.bootstrap_debug_log.append(f"BITS stderr: {result.stderr[:200]}")
                except Exception as e:
                    self.bootstrap_debug_log.append(f"BITS Exception: {str(e)}")

            # 3. Try PowerShell standard fallback
            if not download_success:
                try:
                    self.update_bootstrap_status(self._t("retry_web"))
                    self.after(0, lambda: self.progress_bar.set(0.5))
                    self.bootstrap_debug_log.append("Attempt 3: System.Net.WebClient...")
                    if os.path.exists(temp_zip): os.remove(temp_zip)
                    ps_cmd = f"powershell -Command \"[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object System.Net.WebClient).DownloadFile('{url}', '{temp_zip}')\""
                    result = subprocess.run(ps_cmd, shell=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                    if result.returncode == 0 and self.validate_zip(temp_zip):
                        download_success = True
                    else:
                        self.bootstrap_debug_log.append(f"WebClient failed. ReturnCode: {result.returncode}")
                        if result.stderr: self.bootstrap_debug_log.append(f"WebClient stderr: {result.stderr[:200]}")
                except Exception as e:
                    self.bootstrap_debug_log.append(f"WebClient Exception: {str(e)}")

            if not download_success:
                error_msg = self._t("download_failed")
                if os.path.exists(temp_zip):
                    try:
                        with open(temp_zip, 'rb') as f:
                            leak = f.read(100)
                            self.bootstrap_debug_log.append(f"Downloaded content teaser: {leak}")
                    except: pass
                raise Exception(error_msg)

            self.update_bootstrap_status(self._t("extracting"))
            self.after(0, lambda: self.progress_bar.set(0.8))
            
            with zipfile.ZipFile(temp_zip, 'r') as z:
                z.extractall(path)
                
            if os.path.exists(temp_zip): 
                os.remove(temp_zip)
                
            self.update_bootstrap_status(self._t("bootstrap_done"))
            self.after(0, lambda: self.progress_bar.set(1.0))
            self.after(1000, lambda: self.finish_setup_after_bootstrap(path))
            
        except Exception as e:
            self.update_bootstrap_status(f"Error: {str(e)}")
            self.bootstrap_debug_log.append(f"FATAL ERROR: {str(e)}")
            # Try to save log to disk as ultimate fallback
            try:
                with open("bootstrap_debug.log", "w") as f:
                    f.write("\n".join(self.bootstrap_debug_log))
                self.bootstrap_debug_log.append("Log also saved to 'bootstrap_debug.log'")
            except: pass
            
            self.after(0, lambda: self.add_retry_button(path))
            self.after(0, self.show_debug_log) # Auto-show on failure

    def validate_zip(self, file_path):
        """ Checks if file is a valid ZIP (starts with PK and size > 1MB) """
        try:
            if not os.path.exists(file_path): 
                self.bootstrap_debug_log.append(f"Validation: File missing at {file_path}")
                return False
            size = os.path.getsize(file_path)
            if size < 1024 * 1024: 
                self.bootstrap_debug_log.append(f"Validation: File too small ({size} bytes)")
                return False
            with open(file_path, 'rb') as f:
                header = f.read(2)
                if header == b'PK':
                    return True
                else:
                    self.bootstrap_debug_log.append(f"Validation: Invalid header '{header}'")
                    return False
        except Exception as e:
            self.bootstrap_debug_log.append(f"Validation Exception: {str(e)}")
            return False

    def update_bootstrap_status(self, text):
        self.after(0, lambda: self.bootstrap_label.configure(text=text))

    def add_retry_button(self, path):
        ctk.CTkButton(self.overlay, text=self._t("retry_dl_btn"), command=lambda: self.show_bootstrap_ui(path),
                       fg_color="#3e4a3d", hover_color="#4e5b4d").pack(pady=10)
        ctk.CTkButton(self.overlay, text=self._t("show_debug_btn"), command=self.show_debug_log,
                       fg_color="#444444", hover_color="#555555").pack(pady=5)
        ctk.CTkButton(self.overlay, text=self._t("back_btn"), command=self.setup_ui).pack(pady=5)

    def show_debug_log(self):
        log_win = ctk.CTkToplevel(self)
        log_win.title(self._t("debug_info_btn"))
        log_win.geometry("600x400")
        log_win.attributes("-topmost", True)
        
        txt = ctk.CTkTextbox(log_win, width=580, height=380)
        txt.pack(padx=10, pady=10)
        txt.insert("0.0", "\n".join(self.bootstrap_debug_log))
        txt.configure(state="disabled")

    def finish_setup_after_bootstrap(self, path):
        self.save_config(path)
        self.setup_ui()

    def show_main_view(self):
        # Clear overlay for main
        for widget in self.overlay.winfo_children():
            widget.destroy()
            
        self.label = ctk.CTkLabel(self.overlay, text=self._t("app_title"), font=("Cinzel", 36, "bold"), text_color="#d4af37")
        self.label.pack(pady=(20, 2))
        self.sub_label = ctk.CTkLabel(self.overlay, text=self._t("app_subtitle"), font=("Arial", 11, "bold", "italic"), text_color="#c0c0c0")
        self.sub_label.pack(pady=(0, 15))

        # Password Frame
        self.pass_frame = ctk.CTkFrame(self.overlay, fg_color="transparent")
        self.pass_frame.pack(pady=10, padx=30, fill="x")

        self.pass_label = ctk.CTkLabel(self.pass_frame, text=self._t("pass_label"), font=("Arial", 13, "bold"), text_color="#d4af37")
        self.pass_label.pack(side="left", padx=(0, 10))

        self.password_var = ctk.StringVar(value=self.read_password())
        self.password_var.trace_add("write", self.on_password_change)
        self.password_entry = ctk.CTkEntry(self.pass_frame, textvariable=self.password_var, 
                                           width=200, height=35,
                                           fg_color="#1a1a1a", border_color="#d4af37",
                                           text_color="white")
        self.password_entry.pack(side="right", expand=True, fill="x")

        self.pass_note = ctk.CTkLabel(self.overlay, text=self._t("pass_note"), 
                                      font=("Arial", 10), text_color="#888888")
        self.pass_note.pack(pady=(0, 5))

        # Modpack Selector
        self.mod_frame = ctk.CTkFrame(self.overlay, fg_color="transparent")
        self.mod_frame.pack(pady=5)
        
        self.mod_label = ctk.CTkLabel(self.mod_frame, text=self._t("mod_label"), font=("Arial", 12, "bold"), text_color="#d4af37")
        self.mod_label.pack(pady=(0, 5))
        
        current_mod = self.read_config_value('modpack', "Vanilla")
        self.modpack_var.set(current_mod)
        
        self.mod_selector = ctk.CTkSegmentedButton(self.mod_frame, 
                                                   values=[self._t("vanilla"), self._t("qol"), self._t("diablo")],
                                                   variable=self.modpack_var,
                                                   command=self.on_modpack_change,
                                                   fg_color="#1a1a1a",
                                                   selected_color="#3e4a3d",
                                                   selected_hover_color="#4e5b4d",
                                                   unselected_color="#222222",
                                                   unselected_hover_color="#333333",
                                                   text_color="white")
        self.mod_selector.pack(padx=20)

        # Buttons
        self.button_frame = ctk.CTkFrame(self.overlay, fg_color="transparent")
        self.button_frame.pack(pady=15)

        # Seamless Column
        self.seamless_col = ctk.CTkFrame(self.button_frame, fg_color="transparent")
        self.seamless_col.pack(side="left", padx=15)

        self.seamless_btn = ctk.CTkButton(self.seamless_col, text=self._t("seamless_btn"), 
                                          command=self.launch_seamless,
                                          height=50, width=200,
                                          font=("Arial", 15, "bold"),
                                          fg_color="#3e4a3d", hover_color="#4e5b4d",
                                          border_width=1, border_color="#d4af37",
                                          cursor="hand2")
        self.seamless_btn.pack()
        
        self.seamless_desc = ctk.CTkLabel(self.seamless_col, text=self._t("seamless_desc"), 
                                          font=("Arial", 10), text_color="#aaaaaa")
        self.seamless_desc.pack(pady=(5, 0))

        # Online Column
        self.online_col = ctk.CTkFrame(self.button_frame, fg_color="transparent")
        self.online_col.pack(side="left", padx=15)

        self.online_btn = ctk.CTkButton(self.online_col, text=self._t("online_btn"), 
                                        command=self.launch_online,
                                        height=50, width=200,
                                        font=("Arial", 15, "bold"),
                                        fg_color="#1a1a1a", border_width=2, border_color="#d4af37",
                                        hover_color="#2a2a2a",
                                        cursor="hand2")
        self.online_btn.pack()

        self.online_desc = ctk.CTkLabel(self.online_col, text=self._t("online_desc"), 
                                        font=("Arial", 10), text_color="#aaaaaa")
        self.online_desc.pack(pady=(5, 0))

        self.status_label = ctk.CTkLabel(self.overlay, text="", text_color="gray", font=("Arial", 11))
        self.status_label.pack(pady=5)

        # Troubleshooting Tools
        self.tools_frame = ctk.CTkFrame(self.overlay, fg_color="transparent")
        self.tools_frame.pack(side="bottom", pady=10)
        
        ctk.CTkButton(self.tools_frame, text=self._t("change_path"), 
                       command=self.change_game_path,
                       height=24, width=120,
                       font=("Arial", 10),
                       fg_color="#1a1a1a", hover_color="#333333",
                       text_color="#888888").pack(side="left", padx=5)
                       
        ctk.CTkButton(self.tools_frame, text=self._t("repair_files"), 
                       command=self.repair_modpack,
                       height=24, width=120,
                       font=("Arial", 10),
                       fg_color="#1a1a1a", hover_color="#3e4a3d",
                       text_color="#888888").pack(side="left", padx=5)

        # Start background monitor
        self.monitor_process()

    def add_language_selector(self, parent):
        lang_frame = ctk.CTkFrame(parent, fg_color="transparent")
        lang_frame.place(relx=1.0, rely=0.0, anchor="ne")
        
        current_display = "English"
        for code, name in LANGUAGES_LIST:
            if code == self.lang_var.get():
                current_display = name
                break
                
        lang_menu = ctk.CTkComboBox(lang_frame, 
                                     values=[n for c, n in LANGUAGES_LIST],
                                     command=self.on_lang_change,
                                     width=100, height=22,
                                     font=("Arial", 10),
                                     fg_color="#1a1a1a", border_color="#d4af37",
                                     button_color="#d4af37", button_hover_color="#b48f17")
        lang_menu.set(current_display)
        lang_menu.pack()

    def monitor_process(self):
        if self.is_game_running():
            self.update_status(self._t("now_running"), "#44ff44")
        else:
            # If it was previously "Launching..." but game isn't running yet, keep it for a bit
            current_status = self.status_label.cget("text")
            if "Launching" not in current_status or "found" in current_status:
                self.update_status(self._t("ready"), "gray")
        
        # Check every 2 seconds
        self.after(2000, self.monitor_process)

    def fade_in(self):
        alpha = self.attributes("-alpha")
        if alpha < 1.0:
            alpha += 0.1
            if alpha > 1.0: alpha = 1.0
            self.attributes("-alpha", alpha)
            self.after(30, self.fade_in)
        else:
            self.lift()
            self.focus_force()

    def read_password(self):
        try:
            if os.path.exists(self.settings_path):
                config = configparser.ConfigParser()
                config.read(self.settings_path)
                if 'Settings' in config:
                    return config['Settings'].get('cooppassword', "")
                else:
                    with open(self.settings_path, 'r') as f:
                        for line in f:
                            if "cooppassword" in line:
                                return line.split("=")[1].strip()
            return ""
        except Exception as e:
            print(f"Error reading password: {e}")
            return ""

    def on_password_change(self, *args):
        self.save_password(show_status=False)

    def save_password(self, show_status=True):
        password = self.password_var.get()
        try:
            if os.path.exists(self.settings_path):
                with open(self.settings_path, 'r') as f:
                    lines = f.readlines()
                
                new_lines = []
                found = False
                for line in lines:
                    if line.strip().startswith("cooppassword"):
                        new_lines.append(f"cooppassword = {password}\n")
                        found = True
                    else:
                        new_lines.append(line)
                
                if not found:
                    new_lines.append(f"\ncooppassword = {password}\n")

                with open(self.settings_path, 'w') as f:
                    f.writelines(new_lines)
                if show_status:
                    self.status_label.configure(text=self._t("settings_saved"), text_color="#d4af37")
                return True
            else:
                self.status_label.configure(text=self._t("settings_not_found"), text_color="#ff4444")
                return False
        except Exception as e:
            self.status_label.configure(text=f"{self._t('save_error_prefix')} {e}", text_color="#ff4444")
            return False

    def toggle_dlls(self, mode):
        ersc_enabled = os.path.join(self.game_dir, "ersc.dll")
        ersc_disabled = os.path.join(self.game_dir, "ersc.dll.disabled")
        waygate_enabled = os.path.join(self.game_dir, "waygate_client.dll")
        waygate_disabled = os.path.join(self.game_dir, "waygate_client.dll.disabled")

        try:
            if mode == "seamless":
                if os.path.exists(ersc_disabled):
                    if os.path.exists(ersc_enabled): os.remove(ersc_enabled)
                    os.rename(ersc_disabled, ersc_enabled)
                if os.path.exists(waygate_enabled):
                    if os.path.exists(waygate_disabled): os.remove(waygate_disabled)
                    os.rename(waygate_enabled, waygate_disabled)
            else:
                if os.path.exists(ersc_enabled):
                    if os.path.exists(ersc_disabled): os.remove(ersc_disabled)
                    os.rename(ersc_enabled, ersc_disabled)
                if os.path.exists(waygate_disabled):
                    if os.path.exists(waygate_enabled): os.remove(waygate_enabled)
                    os.rename(waygate_disabled, waygate_enabled)
            return True
        except Exception as e:
            self.status_label.configure(text=f"{self._t('dll_error_prefix')} {e}", text_color="#ff4444")
            return False

    def is_game_running(self):
        try:
            # Check for eldenring.exe in the process list
            # We use the full path if possible to be specific, or just the name
            output = subprocess.check_output('tasklist /FI "IMAGENAME eq eldenring.exe" /NH', shell=True).decode('utf-8', errors='ignore')
            return "eldenring.exe" in output.lower()
        except:
            return False

    def on_modpack_change(self, value):
        # Map translated value back to internal key
        internal_key = "Vanilla"
        if value == self._t("qol"): internal_key = "Quality of Life"
        elif value == self._t("diablo"): internal_key = "Diablo Loot (RNG)"
        
        self.save_config_value("modpack", internal_key)
        self.update_status(f"{self._t('mod_label')} {value}")
        if self.game_dir and not self.is_game_running():
            self.apply_modpack(internal_key)

    def apply_modpack(self, pack_name):
        if not self.game_dir or not os.path.exists(self.game_dir):
            print(f"{self._t('apply_modpack_failed')}")
            return

        # Mapping names to folder-friendly IDs
        pack_map = {
            "Vanilla": "vanilla",
            "Quality of Life": "qol",
            "Diablo Loot (RNG)": "diablo"
        }
        
        pack_id = pack_map.get(pack_name, "vanilla")
        modpacks_dir = os.path.join(self.game_dir, "modpacks")
        source_bin = os.path.join(modpacks_dir, pack_id, "regulation.bin")
        target_bin = os.path.join(self.game_dir, "regulation.bin")

        try:
            if os.path.exists(source_bin):
                import shutil
                shutil.copy2(source_bin, target_bin)
                print(f"Applied regulation.bin for: {pack_name}")
            else:
                if pack_name != "Vanilla":
                    print(f"Modpack file not found: {source_bin}")
            
            # Now update the TOML config
            self.update_toml_config(self.game_dir, pack_name)
            
        except Exception as e:
            print(f"Error applying modpack: {e}")

    def update_toml_config(self, game_path, pack_name):
        toml_path = os.path.join(game_path, "config_eldenring.toml")
        if not os.path.exists(toml_path):
            print(f"TOML config not found: {toml_path}")
            return

        # Define configurations
        configs = {
            "Vanilla": {
                "dlls": '["ersc.dll", "Scripts-Data-Exposer-FS.dll", "waygate_client.dll"]',
                "mods": '[{ enabled = false, name = "modpack", path = "modpack" }]'
            },
            "Quality of Life": {
                "dlls": '["er_alt_saves.dll", "ersc.dll", "erquestlog.dll", "Scripts-Data-Exposer-FS.dll", "waygate_client.dll"]',
                "mods": '[{ enabled = true, name = "mod_qol", path = "mod_qol" }]'
            },
            "Diablo Loot (RNG)": {
                "dlls": '["er_alt_saves.dll", "ersc.dll", "erquestlog.dll", "Scripts-Data-Exposer-FS.dll", "waygate_client.dll"]',
                "mods": '[{ enabled = true, name = "mod_rng", path = "mod_rng" }]'
            }
        }

        config = configs.get(pack_name, configs["Vanilla"])
        
        try:
            with open(toml_path, 'r', encoding='utf-8') as f:
                content = f.read()

            import re
            # Update external_dlls (supports single line or multi-line)
            content = re.sub(r'external_dlls\s*=\s*\[.*?\]', f'external_dlls = {config["dlls"]}', content, flags=re.S)
            # Update mods (supports single line or multi-line)
            content = re.sub(r'mods\s*=\s*\[.*?\]', f'mods = {config["mods"]}', content, flags=re.S)

            with open(toml_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Updated TOML config for {pack_name}")
        except Exception as e:
            print(f"Error updating TOML config: {e}")

    def save_config_value(self, key, value):
        config = configparser.ConfigParser()
        if os.path.exists(self.config_path):
            config.read(self.config_path)
        
        if 'Main' not in config:
            config['Main'] = {}
        
        config['Main'][key] = value
        with open(self.config_path, 'w') as f:
            config.write(f)

    def read_config_value(self, key, fallback=None):
        try:
            if os.path.exists(self.config_path):
                config = configparser.ConfigParser()
                config.read(self.config_path)
                if 'Main' in config:
                    return config['Main'].get(key, fallback)
        except: pass
        return fallback

    def launch_seamless(self):
        if self.is_game_running():
            self.update_status(self._t("running"), "#ff4444")
            return

        # Ensure modpack is applied before launch
        self.apply_modpack(self.modpack_var.get())
        if not self.save_password(): return
        if not self.toggle_dlls("seamless"): return
        if os.path.exists(self.launch_exe):
            self.update_status(self._t("launch_seamless"), "#d4af37")
            subprocess.Popen([self.launch_exe], cwd=self.game_dir)
        else:
            self.update_status(self._t("exe_not_found"), "#ff4444")

    def launch_online(self):
        if self.is_game_running():
            self.update_status(self._t("running"), "#ff4444")
            return
            
        # Ensure modpack is applied before launch (though Online usually needs Vanilla)
        self.apply_modpack(self.modpack_var.get())
        if not self.toggle_dlls("online"): return
        if os.path.exists(self.launch_exe):
            self.update_status(self._t("launch_online"), "#d4af37")
            subprocess.Popen([self.launch_exe], cwd=self.game_dir)
        else:
            self.update_status(self._t("exe_not_found"), "#ff4444")

    def change_game_path(self):
        # Confirm with user? For now just do it
        self.game_dir = None
        self.save_config("")
        self.setup_ui()

    def repair_modpack(self):
        if self.game_dir:
            self.show_bootstrap_ui(self.game_dir)

if __name__ == "__main__":
    app = EldenRingLauncher()
    app.mainloop()
