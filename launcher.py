import os
import time
import webbrowser
import uuid
from datetime import datetime
import shutil
import sys
import subprocess
import configparser
import customtkinter as ctk
import tkinter as tk
import json
import threading
import urllib.request
import zipfile
import io
import ctypes
import struct
import asyncio
import websockets
import queue
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

def is_admin():
    """Detect if the script is running with administrative privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    """Relaunch the script or executable with administrative privileges."""
    if getattr(sys, 'frozen', False):
        # Bundled as EXE
        executable = sys.executable
        params = ' '.join([f'"{arg}"' for arg in sys.argv[1:]])
    else:
        # Running as a Python script
        executable = sys.executable
        params = f'"{os.path.abspath(sys.argv[0])}" ' + ' '.join([f'"{arg}"' for arg in sys.argv[1:]])
    
    try:
        ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, params, None, 1)
        sys.exit(0)
    except Exception as e:
        print(f"Elevation failed: {e}")
        return False

class EldenRingLauncher(ctk.CTk):
    VERSION = "1.1.0"
    VERSION_URL = "https://raw.githubusercontent.com/conan513/er_launcher/master/version.txt"
    UPDATE_URL = "https://github.com/conan513/er_launcher/releases/download/v1/ER_Launcher.exe"

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
        
        self.game_active = False
        
        # QoL Mod Toggles (default all enabled)
        self.qol_questlog_var = ctk.BooleanVar(value=self.read_config_value("qol_questlog_enabled", "True") == "True")
        self.qol_map_var = ctk.BooleanVar(value=self.read_config_value("qol_map_enabled", "True") == "True")
        self.qol_fps_unlocker_var = ctk.BooleanVar(value=self.read_config_value("qol_fps_unlocker_enabled", "True") == "True")
        fps_limit = int(self.read_config_value("qol_fps_limit", "300"))
        self.qol_fps_limit_var = ctk.IntVar(value=min(300, fps_limit))
        self.disable_sharpening_var = ctk.BooleanVar(value=self.read_config_value("disable_sharpening", "True") == "True")
        
        self.chat_nickname_var = ctk.StringVar(value=self.read_config_value("chat_nickname", ""))
        
        # Identity Verification (Tripcodes)
        self.chat_user_id = self.read_config_value("chat_user_id", "")
        if not self.chat_user_id:
            self.chat_user_id = str(uuid.uuid4())
            self.save_config_value("chat_user_id", self.chat_user_id)
            
        self.show_chat = self.read_config_value("show_chat", "True") == "True"
        self.chat_queue = queue.Queue()
        self.chat_socket = None
        self.chat_thread = None
        self.last_send_time = 0 # Anti-spam
        
        self.scroll_frame = None
        self.current_tab_key = "tab_play"
        
        # Set window size based on chat visibility
        initial_width = 1000 if self.show_chat else 660
        self.center_window(initial_width, 550)
        
        # Set Window Icon
        self.icon_path = resource_path("app_icon.ico")
        if os.path.exists(self.icon_path):
            self.after(200, lambda: self.iconbitmap(self.icon_path))
        
        # Set theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.game_dir = None
        self.load_config()

        # UI Scaling Setup
        scaling_value = self.read_config_value("ui_scaling", "1.0")
        try:
            scale_float = float(scaling_value)
            ctk.set_widget_scaling(scale_float)
            ctk.set_window_scaling(scale_float)
        except Exception as e:
            print(f"Error applying UI scaling: {e}")
            ctk.set_widget_scaling(1.0)
            ctk.set_window_scaling(1.0)

        # Check for updates on startup
        self.check_for_updates()

        # UI Setup (Base)
        self.lockdown_frame = None
        self.setup_ui()
        self.launch_start_time = 0
        
        # Start background monitor
        self.after(2000, self.monitor_process)
        
        # Check for administrative privileges if game is in Program Files
        self.after(1000, self.check_admin_status)

        self.emoji_shortcuts = {
            ":)": "🙂", ":-)": "🙂", ":smile:": "🙂",
            ":D": "😂", ":-D": "😂", ":grin:": "😁",
            "<3": "❤️", ":heart:": "❤️",
            ":(": "☹️", ":-(": "☹️", ":sad:": "😢",
            ":thumbsup:": "👍", ":+1:": "👍",
            ":ok:": "👌",
            ":fire:": "🔥",
            ":skull:": "💀",
            ":check:": "✅",
            ":x:": "❌",
            ":wave:": "👋",
            ":eyes:": "👀",
            ":star:": "🌟",
            ":100:": "💯",
            ":cry:": "😭",
            ":cool:": "😎",
            ":wink:": "😉", ";)": "😉", ";-)": "😉",
            ":thinking:": "🤔",
            ":love:": "😍",
            ":lol:": "🤣"
        }
        
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

    def get_steam_id64(self):
        """Retrieve SteamID64 save folder path, with fallbacks for non-standard folder names."""
        appdata = os.getenv('APPDATA')
        base_dir = os.path.join(appdata, "EldenRing")
        if not os.path.exists(base_dir):
            return None

        # 1. Try Registry (Most accurate if Steam is running)
        try:
            import winreg
            hkey = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam\ActiveProcess")
            active_user, _ = winreg.QueryValueEx(hkey, "ActiveUser")
            winreg.CloseKey(hkey)
            if active_user:
                steam_id64 = str(active_user + 76561197960265728)
                potential_path = os.path.join(base_dir, steam_id64)
                if os.path.exists(potential_path):
                    return potential_path
        except:
            pass

        # 2. Fallback: Search for folders containing ER0000.sl2 or ER0000.co2
        try:
            items = os.listdir(base_dir)
            potential_folders = []
            for item in items:
                item_path = os.path.join(base_dir, item)
                if os.path.isdir(item_path):
                    # Check if it contains save files
                    if any(f.startswith("ER0000") for f in os.listdir(item_path)):
                        # Get last modification time of ER0000.sl2 or any save file
                        mtime = os.path.getmtime(item_path)
                        potential_folders.append((mtime, item_path))
            
            if potential_folders:
                # Pick the most recently modified folder that contains saves
                potential_folders.sort(key=lambda x: x[0], reverse=True)
                return potential_folders[0][1]
        except Exception as e:
            print(f"Error searching for save folder: {e}")

        return None


    def open_saves_folder(self):
        """Open the Elden Ring saves folder in Windows Explorer."""
        save_folder = self.get_steam_id64()
        if not save_folder:
            self.update_status(self._t("save_folder_not_found"), "#ff4444")
            return
        
        if os.path.exists(save_folder):
            # Open folder in Windows Explorer
            subprocess.Popen(f'explorer "{save_folder}"')
            self.update_status(self._t("save_folder_opened"), "#44ff44")
        else:
            self.update_status(self._t("save_folder_not_found"), "#ff4444")

    def is_path_protected(self, path):
        """Check if the given path is in a protected system directory."""
        if not path:
            return False
            
        protected_folders = [
            os.environ.get("ProgramFiles", "C:\\Program Files"),
            os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"),
            os.environ.get("SystemRoot", "C:\\Windows")
        ]
        
        for protected in protected_folders:
            if path.lower().startswith(protected.lower()):
                return True
        return False

    def check_admin_status(self):
        """Check if the launcher needs administrator privileges based on game path."""
        if is_admin():
            # Already running as admin, maybe show a small indicator or just do nothing
            self.update_status(self._t("elevated_privileges"), "#d4af37")
            return

        # Check if game path is in a protected system directory
        if self.game_dir and self.is_path_protected(self.game_dir):
            self.show_admin_elevation_ui()

    def show_admin_elevation_ui(self):
        """Show a button to restart the launcher with administrative privileges."""
        if hasattr(self, 'admin_btn') and self.admin_btn.winfo_exists():
            return # Already showing

        if hasattr(self, 'overlay') and self.overlay.winfo_exists():
            # Add a more prominent button if elevation is required
            self.admin_btn = ctk.CTkButton(self.overlay, 
                                           text=f"🛡️ {self._t('restart_as_admin')}",
                                           command=run_as_admin,
                                           height=30, width=250,
                                           font=("Arial", 11, "bold"),
                                           fg_color="#8b1a1a", hover_color="#a82222",
                                           border_width=1, border_color="#d4af37")
            
            # Ensure setup_status/status_label can wrap the long admin text
            if hasattr(self, 'setup_status') and self.setup_status.winfo_exists():
                self.setup_status.configure(wraplength=480)
            if hasattr(self, 'status_label') and self.status_label.winfo_exists():
                self.status_label.configure(wraplength=480)

            # Insert above the status label if possible, or just pack
            if hasattr(self, 'status_label') and self.status_label.winfo_exists():
                self.admin_btn.pack(pady=10, after=self.status_label)
            elif hasattr(self, 'setup_status') and self.setup_status.winfo_exists():
                self.admin_btn.pack(pady=10, after=self.setup_status)
            else:
                self.admin_btn.pack(pady=10)
                
            self.update_status(self._t("admin_required"), "#ff4444")
            self.update_setup_status(self._t("admin_required"))


    def _t(self, key):
        lang = self.lang_var.get()
        # Fallback to English if key missing in translation
        return TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, TRANSLATIONS["en"].get(key, key))

    def on_lang_change(self, value):
        # Save current tab key before refreshing
        if hasattr(self, 'tabview') and self.tabview.winfo_exists():
            current_name = self.tabview.get()
            for key in ["tab_play", "tab_settings", "tab_tools"]:
                if self._t(key) == current_name:
                    self.current_tab_key = key
                    break

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
        self.lockdown_frame = None
        for widget in self.winfo_children():
            widget.destroy()

        # Background Image
        self.bg_image_path = resource_path("background.png")
        if os.path.exists(self.bg_image_path):
            bg_pil = Image.open(self.bg_image_path)
            self.bg_image = ctk.CTkImage(light_image=bg_pil, dark_image=bg_pil, size=(1000, 550))
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
            
        # Language Selector outside the frames (only during setup)
        if not self.game_dir:
            self.add_language_selector(self)
            
        # Ensure window is visible and fades in
        self.update() # Force update to map window
        self.fade_in()

    def show_setup_view(self):
        # Restore overlay for setup
        self.overlay.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.85, relheight=0.9)
        self.overlay.configure(fg_color="#151515", border_width=1)
        
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
        
        self.setup_status = ctk.CTkLabel(self.overlay, text="", font=("Arial", 11), text_color="gray", wraplength=480)
        self.setup_status.pack(pady=10)

    def start_auto_discovery(self):
        self.found_paths_set.clear()
        self.search_btn.configure(state="disabled", text=self._t("searching"))
        threading.Thread(target=self.run_discovery, daemon=True).start()

    def run_discovery(self):
        # 0. Check Local Folder (Contextual Discovery)
        self.update_setup_status(self._t("searching"))
        
        # Check launcher_base itself
        if os.path.exists(os.path.join(self.launcher_base, "eldenring.exe")):
            self.after(0, lambda: self.handle_single_path_found(self.launcher_base))
            
        # Check launcher_base/Game
        local_game_path = os.path.join(self.launcher_base, "Game")
        if os.path.exists(os.path.join(local_game_path, "eldenring.exe")):
            self.after(0, lambda: self.handle_single_path_found(local_game_path))

        # 1. Check Registry (Steam)
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
        
        self.setup_status = ctk.CTkLabel(self.overlay, text=self._t("searching_more"), font=("Arial", 11), text_color="gray", wraplength=480)
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

    def show_admin_required_view(self, path):
        # Clear overlay
        for widget in self.overlay.winfo_children():
            widget.destroy()
            
        ctk.CTkLabel(self.overlay, text=f"🛡️ {self._t('admin_required')}", 
                     font=("Cinzel", 18, "bold"), text_color="#ff4444", wraplength=480).pack(pady=(30, 20))
        
        path_box = ctk.CTkTextbox(self.overlay, width=500, height=60, fg_color="#1a1a1a", text_color="#aaaaaa", font=("Consolas", 11))
        path_box.pack(pady=10, padx=20)
        path_box.insert("0.0", f"Target: {path}")
        path_box.configure(state="disabled")

        ctk.CTkLabel(self.overlay, text=self._t("tip_4"), 
                      font=("Arial", 13), text_color="#aaaaaa", wraplength=500).pack(pady=10)
        
        btn_frame = ctk.CTkFrame(self.overlay, fg_color="transparent")
        btn_frame.pack(pady=30)
        
        ctk.CTkButton(btn_frame, text=f"🛡️ {self._t('restart_as_admin')}", command=run_as_admin,
                       fg_color="#8b1a1a", hover_color="#a82222", width=220, height=40, font=("Arial", 12, "bold"),
                       border_width=1, border_color="#d4af37").pack(side="left", padx=10)
                       
        ctk.CTkButton(btn_frame, text=self._t("back_btn"), command=self.show_setup_view,
                       fg_color="#333333", hover_color="#444444", width=150, height=40).pack(side="left", padx=10)

    def complete_setup(self, path):
        # 1. Proactive Admin Check - Blocked view for protected paths
        if not is_admin() and self.is_path_protected(path):
            self.show_admin_required_view(path)
            return

        # 2. Standardize folder name to "Game" (case-insensitive check)
        folder_name = os.path.basename(path)
        if folder_name.lower() != "game":
            new_path = os.path.join(path, "Game")
            print(f"Standardizing: Creating nested 'Game' folder at {new_path}")
            
            try:
                # Create the Game subfolder if it doesn't exist
                if not os.path.exists(new_path):
                    os.makedirs(new_path)
                
                # Move all items from 'path' into 'new_path', except 'Game' itself and the launcher
                current_exe = os.path.basename(sys.executable) if getattr(sys, 'frozen', False) else os.path.basename(sys.argv[0])
                
                for item in os.listdir(path):
                    item_path = os.path.join(path, item)
                    if item.lower() == "game" or item == current_exe:
                        continue
                        
                    try:
                        shutil.move(item_path, new_path)
                    except Exception as move_err:
                        print(f"Warning: Could not move {item}: {move_err}")
                
                path = new_path
                print(f"Standardized: Content moved to {path}")
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

        # Add Admin Elevation button directly to error screen
        if not is_admin():
            self.error_admin_btn = ctk.CTkButton(self.overlay, 
                                                 text=f"🛡️ {self._t('restart_as_admin')}",
                                                 command=run_as_admin,
                                                 height=35, width=280,
                                                 font=("Arial", 12, "bold"),
                                                 fg_color="#8b1a1a", hover_color="#a82222",
                                                 border_width=1, border_color="#d4af37")
            self.error_admin_btn.pack(pady=10)

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
        btn_frame = ctk.CTkFrame(self.overlay, fg_color="transparent")
        btn_frame.pack(pady=10)

        ctk.CTkButton(btn_frame, text=self._t("retry_dl_btn"), command=lambda: self.show_bootstrap_ui(path),
                       fg_color="#3e4a3d", hover_color="#4e5b4d", width=140).pack(side="left", padx=5)
                       
        ctk.CTkButton(btn_frame, text=self._t("show_debug_btn"), command=self.show_debug_log,
                       fg_color="#444444", hover_color="#555555", width=140).pack(side="left", padx=5)
                       
        ctk.CTkButton(self.overlay, text=self._t("back_btn"), command=self.setup_ui, width=290).pack(pady=5)

        # Add Admin Elevation button if it failed and we're not admin
        if not is_admin():
            self.bootstrap_admin_btn = ctk.CTkButton(self.overlay, 
                                                     text=f"🛡️ {self._t('restart_as_admin')}",
                                                     command=run_as_admin,
                                                     height=35, width=290,
                                                     font=("Arial", 12, "bold"),
                                                     fg_color="#8b1a1a", hover_color="#a82222",
                                                     border_width=1, border_color="#d4af37")
            self.bootstrap_admin_btn.pack(pady=10)

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
        # Hide the setup overlay
        self.overlay.place_forget()
        
        # Cleanup any previous main view frames if refreshing
        if hasattr(self, 'content_frame'):
            try: self.content_frame.destroy()
            except: pass
        if hasattr(self, 'sidebar_frame'):
            try: self.sidebar_frame.destroy()
            except: pass
            
        # Left Side (Main Content Panel) - Placed directly on self for transparency
        self.content_frame = ctk.CTkFrame(self, fg_color="#151515", corner_radius=15, border_width=1, border_color="#d4af37")
        
        # Position based on chat visibility
        if self.show_chat:
            self.content_frame.place(relx=0.02, rely=0.05, relwidth=0.64, relheight=0.9)
        else:
            self.content_frame.place(relx=0.05, rely=0.05, relwidth=0.9, relheight=0.9)
        
        # Right Side (Chat Panel) - Placed directly on self for transparency
        self.sidebar_frame = ctk.CTkFrame(self, fg_color="#151515", corner_radius=15, border_width=1, border_color="#d4af37")
        if self.show_chat:
            self.sidebar_frame.place(relx=0.68, rely=0.05, relwidth=0.30, relheight=0.9)
            
        # Top Header Frame for Title and Toggle
        self.header_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.header_frame.pack(fill="x", pady=(10, 0), padx=20)
        
        self.label = ctk.CTkLabel(self.header_frame, text=self._t("app_title"), font=("Cinzel", 36, "bold"), text_color="#d4af37")
        self.label.pack(side="left", expand=True, padx=(50, 0)) # Push to center
        
        # Chat Toggle Button
        toggle_text = self._t("chat_hide") if self.show_chat else self._t("chat_show")
        self.chat_toggle_btn = ctk.CTkButton(self.header_frame, text=toggle_text, width=100, height=25,
                                             font=("Arial", 10, "bold"),
                                             fg_color="#1a1a1a", border_width=1, border_color="#d4af37",
                                             command=self.toggle_chat)
        self.chat_toggle_btn.pack(side="right")

        self.sub_label = ctk.CTkLabel(self.content_frame, text=self._t("app_subtitle"), font=("Arial", 11, "bold", "italic"), text_color="#c0c0c0")
        self.sub_label.pack(pady=(0, 10))

        # Create Tabview (in content_frame)
        self.tabview = ctk.CTkTabview(self.content_frame, fg_color="transparent", 
                                        segmented_button_selected_color="#3e4a3d",
                                        segmented_button_selected_hover_color="#4e5b4d",
                                        segmented_button_unselected_hover_color="#333333",
                                        text_color="white")
        self.tabview.pack(padx=20, pady=(0, 5), fill="both", expand=True)

        self.tab_play = self.tabview.add(self._t("tab_play"))
        self.tab_settings = self.tabview.add(self._t("tab_settings"))
        self.tab_tools = self.tabview.add(self._t("tab_tools"))
        self.tab_about = self.tabview.add(self._t("tab_about"))
        
        # Restore active tab with a robust fallback
        try:
            target_tab_name = self._t(self.current_tab_key)
            if target_tab_name != self._t("tab_chat"): # Skip chat tab as it's now in sidebar
                self.tabview.set(target_tab_name)
            else:
                self.tabview.set(self._t("tab_play"))
        except Exception:
            try:
                self.tabview.set(self._t("tab_play"))
            except:
                pass

        # --- CHAT SIDEBAR ---
        self.setup_chat_sidebar(self.sidebar_frame)

        # --- PLAY TAB ---

        self.mod_frame = ctk.CTkFrame(self.tab_play, fg_color="transparent")
        self.mod_frame.pack(pady=10)
        
        self.mod_label = ctk.CTkLabel(self.mod_frame, text=self._t("mod_label"), font=("Arial", 12, "bold"), text_color="#d4af37")
        self.mod_label.pack(pady=(0, 5))
        
        current_mod = self.read_config_value('modpack', "Vanilla")
        self.modpack_var.set(current_mod)
        
        self.mod_selector = ctk.CTkSegmentedButton(self.mod_frame, 
                                                   values=[self._t("vanilla"), self._t("qol"), self._t("diablo")],
                                                   variable=self.modpack_var,
                                                   command=self.on_modpack_change,
                                                   fg_color="#1a1a1a")
        self.mod_selector.pack(padx=20)

        # Launch Buttons
        self.button_frame = ctk.CTkFrame(self.tab_play, fg_color="transparent")
        self.button_frame.pack(pady=15)

        # Seamless Column
        self.seamless_col = ctk.CTkFrame(self.button_frame, fg_color="transparent")
        self.seamless_col.pack(side="left", padx=10)

        self.seamless_btn = ctk.CTkButton(self.seamless_col, text=self._t("seamless_btn"), 
                                          command=self.launch_seamless,
                                          height=45, width=180,
                                          font=("Arial", 14, "bold"),
                                          fg_color="#3e4a3d", hover_color="#4e5b4d",
                                          border_width=1, border_color="#d4af37")
        self.seamless_btn.pack()
        
        self.seamless_desc = ctk.CTkLabel(self.seamless_col, text=self._t("seamless_desc"), 
                                          font=("Arial", 9), text_color="#aaaaaa")
        self.seamless_desc.pack(pady=(5, 0))

        # Online Column
        self.online_col = ctk.CTkFrame(self.button_frame, fg_color="transparent")
        self.online_col.pack(side="left", padx=10)

        self.online_btn = ctk.CTkButton(self.online_col, text=self._t("online_btn"), 
                                        command=self.launch_online,
                                        height=45, width=180,
                                        font=("Arial", 14, "bold"),
                                        fg_color="#1a1a1a", border_width=2, border_color="#d4af37")
        self.online_btn.pack()

        self.online_desc = ctk.CTkLabel(self.online_col, text=self._t("online_desc"), 
                                        font=("Arial", 9), text_color="#aaaaaa")
        self.online_desc.pack(pady=(5, 0))

        # Save Converter Section (Moved here for better visibility)
        self.conv_frame = ctk.CTkFrame(self.tab_play, fg_color="transparent")
        self.conv_frame.pack(pady=(20, 0), padx=30, fill="x")

        self.conv_var = ctk.StringVar(value=self.read_config_value("auto_save_converter", "0"))
        self.conv_checkbox = ctk.CTkCheckBox(self.conv_frame, text=self._t("save_converter_label"),
                                              variable=self.conv_var,
                                              onvalue="1", offvalue="0",
                                              command=lambda: self.save_config_value("auto_save_converter", self.conv_var.get()),
                                              font=("Arial", 12, "bold"), text_color="#d4af37",
                                              fg_color="#3e4a3d", hover_color="#4e5b4d")
        self.conv_checkbox.pack(pady=(0, 2))

        self.conv_desc = ctk.CTkLabel(self.conv_frame, text=self._t("save_converter_desc"),
                                      font=("Arial", 9), text_color="#888888", justify="center", wraplength=450)
        self.conv_desc.pack(pady=(0, 5))

        self.update_save_converter_state()

        # --- SETTINGS TAB ---
        # Password Section
        self.pass_frame = ctk.CTkFrame(self.tab_settings, fg_color="transparent")
        self.pass_frame.pack(pady=(20, 5), padx=30, fill="x")

        self.pass_label = ctk.CTkLabel(self.pass_frame, text=self._t("pass_label"), font=("Arial", 13, "bold"), text_color="#d4af37")
        self.pass_label.pack(side="left", padx=(0, 10))

        self.password_var = ctk.StringVar(value=self.read_password())
        self.password_var.trace_add("write", self.on_password_change)
        self.password_entry = ctk.CTkEntry(self.pass_frame, textvariable=self.password_var, 
                                           width=200, height=35,
                                           fg_color="#1a1a1a", border_color="#d4af37")
        self.password_entry.pack(side="right", expand=True, fill="x")

        self.pass_note = ctk.CTkLabel(self.tab_settings, text=self._t("pass_note"), 
                                      font=("Arial", 10), text_color="#888888")
        self.pass_note.pack(pady=(0, 20))

        # Language Selector
        lang_label = ctk.CTkLabel(self.tab_settings, text=self._t("select_lang"), font=("Arial", 12, "bold"), text_color="#d4af37")
        lang_label.pack(pady=(10, 5))
        self.add_language_selector(self.tab_settings)

        # UI Scaling
        scaling_label = ctk.CTkLabel(self.tab_settings, text=self._t("ui_scaling_label"), font=("Arial", 12, "bold"), text_color="#d4af37")
        scaling_label.pack(pady=(15, 5))
        
        current_scaling = self.read_config_value("ui_scaling", "1.0")
        scaling_options = ["100%", "125%", "150%", "175%", "200%"]
        
        # Map float to percentage string for the menu
        scaling_map = {"1.0": "100%", "1.25": "125%", "1.5": "150%", "1.75": "175%", "2.0": "200%"}
        initial_val = scaling_map.get(current_scaling, "100%")
        
        self.scaling_menu = ctk.CTkOptionMenu(self.tab_settings,
                                              values=scaling_options,
                                              command=self.on_scaling_change,
                                              width=150, height=28,
                                              fg_color="#1a1a1a", button_color="#d4af37",
                                              button_hover_color="#b48f17")
        self.scaling_menu.set(initial_val)
        self.scaling_menu.pack()


        # --- TOOLS TAB ---
        ctk.CTkButton(self.tab_tools, text=self._t("open_saves_folder"),
                      command=self.open_saves_folder,
                      height=35, width=250,
                      fg_color="#1a1a1a", hover_color="#2a2a2a",
                      border_width=1, border_color="#d4af37").pack(pady=10)

        ctk.CTkButton(self.tab_tools, text=self._t("change_path"), 
                       command=self.change_game_path,
                       height=35, width=250,
                       fg_color="#1a1a1a", hover_color="#333333",
                       text_color="#aaaaaa").pack(pady=10)
                       
        ctk.CTkButton(self.tab_tools, text=self._t("repair_files"), 
                       command=self.repair_modpack,
                       height=35, width=250,
                       fg_color="#1a1a1a", hover_color="#3e4a3d",
                       text_color="#aaaaaa").pack(pady=10)

        # --- ABOUT TAB ---
        self.setup_about_tab()

        # --- MOD SETTINGS TAB (conditionally shown) ---
        # Check if QoL or Diablo is selected and add tab
        current_mod = self.read_config_value('modpack', "Vanilla")
        if current_mod in ["Quality of Life", "Diablo Loot (RNG)"]:
            self.create_mod_settings_tab()

        # Footer Frame (Status + Update Button)
        self.footer_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.footer_frame.pack(side="bottom", fill="x", pady=10, padx=20)

        # Create Update Button (Hidden by default, parented to footer)
        self.update_btn = ctk.CTkButton(self.footer_frame, text="Update Available!", 
                                        command=self.perform_update,
                                        width=200, height=30,
                                        fg_color="#e15f41", hover_color="#c44569",
                                        font=("Arial", 12, "bold"))

        # Status Label (Inside the footer)
        self.status_label = ctk.CTkLabel(self.footer_frame, text="", text_color="gray", font=("Arial", 11), wraplength=480)
        self.status_label.pack(side="bottom")

    def toggle_chat(self):
        """Toggle chat visibility and resize window."""
        self.show_chat = not self.show_chat
        self.save_config_value("show_chat", str(self.show_chat))
        
        if self.show_chat:
            # Show Chat
            self.geometry("1000x550")
            self.content_frame.place(relx=0.02, rely=0.05, relwidth=0.64, relheight=0.9)
            self.sidebar_frame.place(relx=0.68, rely=0.05, relwidth=0.30, relheight=0.9)
            self.chat_toggle_btn.configure(text=self._t("chat_hide"))
        else:
            # Hide Chat
            self.geometry("660x550")
            self.sidebar_frame.place_forget()
            self.content_frame.place(relx=0.05, rely=0.05, relwidth=0.9, relheight=0.9)
            self.chat_toggle_btn.configure(text=self._t("chat_show"))
        
        # Re-center window after resize
        self.center_window(1000 if self.show_chat else 660, 550)


    def create_mod_settings_tab(self):
        """Create and populate the Mod Settings tab with a two-column layout."""
        self.tab_mod_settings = self.tabview.add(self._t("tab_mod_settings"))
        
        # Container frame for the grid
        self.qol_container = ctk.CTkFrame(self.tab_mod_settings, fg_color="transparent")
        self.qol_container.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Configure grid columns for equal width
        self.qol_container.grid_columnconfigure(0, weight=1)
        self.qol_container.grid_columnconfigure(1, weight=1)

        # Title (spanning both columns)
        ctk.CTkLabel(self.qol_container, text=self._t("mod_settings_title"), 
                     font=("Arial", 14, "bold"), text_color="#d4af37").grid(row=0, column=0, columnspan=2, pady=(10, 5))
        
        # --- COLUMN 0 (LEFT) ---
        col0_frame = ctk.CTkFrame(self.qol_container, fg_color="transparent")
        col0_frame.grid(row=1, column=0, sticky="nsew", padx=(10, 5), pady=5)
        
        # Quest Log
        self.qol_questlog_cb = ctk.CTkCheckBox(col0_frame, text=self._t("qol_questlog"),
                                                variable=self.qol_questlog_var,
                                                command=self.on_qol_toggle_change,
                                                font=("Arial", 11, "bold"), text_color="#d4af37",
                                                fg_color="#3e4a3d", hover_color="#4e5b4d")
        self.qol_questlog_cb.pack(anchor="w", pady=(5, 0))
        ctk.CTkLabel(col0_frame, text=self._t("qol_questlog_desc"),
                     font=("Arial", 8), text_color="#888888", justify="left").pack(anchor="w", padx=(25, 0), pady=(0, 5))
        
        # Map for Goblins
        self.qol_map_cb = ctk.CTkCheckBox(col0_frame, text=self._t("qol_map"),
                                          variable=self.qol_map_var,
                                          command=self.on_qol_toggle_change,
                                          font=("Arial", 11, "bold"), text_color="#d4af37",
                                          fg_color="#3e4a3d", hover_color="#4e5b4d")
        self.qol_map_cb.pack(anchor="w", pady=(5, 0))
        ctk.CTkLabel(col0_frame, text=self._t("qol_map_desc"),
                     font=("Arial", 8), text_color="#888888", justify="left").pack(anchor="w", padx=(25, 0), pady=(0, 5))
        
        # --- COLUMN 1 (RIGHT) ---
        col1_frame = ctk.CTkFrame(self.qol_container, fg_color="transparent")
        col1_frame.grid(row=1, column=1, sticky="nsew", padx=(5, 10), pady=5)
        
        
        # FPS Unlocker
        self.qol_fps_unlocker_cb = ctk.CTkCheckBox(col1_frame, text=self._t("qol_fps_unlocker"),
                                                    variable=self.qol_fps_unlocker_var,
                                                    command=self.on_qol_fps_toggle_change,
                                                    font=("Arial", 11, "bold"), text_color="#d4af37",
                                                    fg_color="#3e4a3d", hover_color="#4e5b4d")
        self.qol_fps_unlocker_cb.pack(anchor="w", pady=(5, 0))
        ctk.CTkLabel(col1_frame, text=self._t("qol_fps_unlocker_desc"),
                     font=("Arial", 8), text_color="#888888", justify="left").pack(anchor="w", padx=(25, 0), pady=(0, 5))
        
        # FPS Limit Slider (compactly shown under checkbox)
        self.fps_limit_frame = ctk.CTkFrame(col1_frame, fg_color="transparent")
        self.fps_limit_frame.pack(anchor="w", padx=(25, 0), pady=(0, 5), fill="x")
        
        self.fps_limit_label = ctk.CTkLabel(self.fps_limit_frame, text=f"{self._t('qol_fps_limit')} {self.qol_fps_limit_var.get()}",
                                            font=("Arial", 10), text_color="#d4af37")
        self.fps_limit_label.pack(anchor="w")
        
        self.fps_limit_slider = ctk.CTkSlider(self.fps_limit_frame, from_=60, to=300, number_of_steps=240,
                                              variable=self.qol_fps_limit_var,
                                              command=self.on_fps_limit_change,
                                              height=16, fg_color="#1a1a1a", progress_color="#3e4a3d",
                                              button_color="#d4af37", button_hover_color="#b48f17")
        self.fps_limit_slider.pack(anchor="w", fill="x", padx=(0, 5))
        
        # Disable Sharpening
        self.disable_sharpening_cb = ctk.CTkCheckBox(col1_frame, text=self._t("disable_sharpening"),
                                                      variable=self.disable_sharpening_var,
                                                      command=self.on_qol_toggle_change,
                                                      font=("Arial", 11, "bold"), text_color="#d4af37",
                                                      fg_color="#3e4a3d", hover_color="#4e5b4d")
        self.disable_sharpening_cb.pack(anchor="w", pady=(10, 0))
        ctk.CTkLabel(col1_frame, text=self._t("disable_sharpening_desc"),
                     font=("Arial", 8), text_color="#888888", justify="left").pack(anchor="w", padx=(25, 0), pady=(0, 5))
        
        # Update FPS limit visibility and Map checkbox
        self.update_fps_limit_visibility()
        self.update_map_checkbox_state()

    def update_map_checkbox_state(self):
        """Enable/disable Map checkbox based on current modpack."""
        current_modpack = self.read_config_value('modpack', "Vanilla")
        
        if current_modpack == "Diablo Loot (RNG)":
            # Disable checkbox and force it to enabled for Diablo
            self.qol_map_var.set(True)
            self.qol_map_cb.configure(state="disabled")
        else:
            # Enable checkbox for QoL
            self.qol_map_cb.configure(state="normal")

    def on_qol_fps_toggle_change(self):
        """Called when FPS Unlocker toggle is changed."""
        self.on_qol_toggle_change()
        self.update_fps_limit_visibility()
    
    def update_fps_limit_visibility(self):
        """Enable/disable FPS limit slider based on FPS Unlocker toggle."""
        if self.qol_fps_unlocker_var.get():
            self.fps_limit_slider.configure(state="normal")
            self.fps_limit_label.configure(text_color="#d4af37")
        else:
            self.fps_limit_slider.configure(state="disabled")
            self.fps_limit_label.configure(text_color="#888888")
    
    def on_fps_limit_change(self, value):
        """Called when FPS limit slider is changed."""
        fps_value = int(value)
        self.qol_fps_limit_var.set(fps_value)
        
        # Update label text
        self.fps_limit_label.configure(text=f"{self._t('qol_fps_limit')} {fps_value}")
        
        # Save to launcher config
        self.save_config_value("qol_fps_limit", str(fps_value))
        
        # Update FPS config.ini if game is not running
        if self.game_dir and not self.is_game_running():
            self.update_fps_config_ini(fps_value)


    def on_qol_toggle_change(self):
        """Called when any QoL toggle is changed."""
        # Save toggle states
        self.save_config_value("qol_questlog_enabled", str(self.qol_questlog_var.get()))
        self.save_config_value("qol_map_enabled", str(self.qol_map_var.get()))
        self.save_config_value("qol_fps_unlocker_enabled", str(self.qol_fps_unlocker_var.get()))
        self.save_config_value("disable_sharpening", str(self.disable_sharpening_var.get()))
        
        if self.game_dir:
            self.toggle_fps_unlocker_file()
            self.toggle_sharpening_file()
        
        # Update TOML and INI configs if game is not running
        if self.game_dir and not self.is_game_running():
            self.update_toml_config(self.game_dir, "Quality of Life")
            
            # Update FPS config.ini if FPS Unlocker is enabled
            if self.qol_fps_unlocker_var.get():
                self.update_fps_config_ini(self.qol_fps_limit_var.get())

    def toggle_fps_unlocker_file(self):
        """Enable/disable FPS Unlocker by renaming the DLL file."""
        if not self.game_dir:
            return
        
        fps_dll_path = os.path.join(self.game_dir, "dinput8.dll")
        fps_dll_disabled = fps_dll_path + ".disabled"
        
        try:
            if self.qol_fps_unlocker_var.get():
                # Enable: rename .dll.disabled to .dll
                if os.path.exists(fps_dll_disabled):
                    os.rename(fps_dll_disabled, fps_dll_path)
                    print(f"Enabled FPS Unlocker: {fps_dll_path}")
            else:
                # Disable: rename .dll to .dll.disabled
                if os.path.exists(fps_dll_path):
                    os.rename(fps_dll_path, fps_dll_disabled)
                    print(f"Disabled FPS Unlocker: {fps_dll_disabled}")
        except Exception as e:
            print(f"Error toggling FPS Unlocker file: {e}")
    
    def toggle_sharpening_file(self):
        """Enable/disable sharpening by renaming the shader file."""
        if not self.game_dir:
            return
        
        # Determine current mod folder based on selected modpack
        pack_map = {
            "Quality of Life": "mod_qol",
            "Diablo Loot (RNG)": "mod_rng"
        }
        mod_folder = pack_map.get(self.modpack_var.get())
        
        # Only apply to QoL and Diablo modpacks
        if not mod_folder:
            return
        
        shader_file = os.path.join(self.game_dir, mod_folder, "shader", "gxposteffect.shaderbnd.dcx")
        shader_disabled = shader_file + ".disabled"
        
        # Check if neither file exists - suggest repair
        if not os.path.exists(shader_file) and not os.path.exists(shader_disabled):
            print(f"Warning: Shader file not found in {mod_folder}/shader/")
            self.update_status(self._t("config_missing_warning").format(file=shader_file), "#ff4444")
            return
        
        try:
            if self.disable_sharpening_var.get():
                # Disable sharpening: ensure file is active (not .disabled)
                if os.path.exists(shader_disabled):
                    os.rename(shader_disabled, shader_file)
                    print(f"Disabled sharpening: {shader_file}")
            else:
                # Enable sharpening: rename file to .disabled
                if os.path.exists(shader_file):
                    os.rename(shader_file, shader_disabled)
                    print(f"Enabled sharpening: {shader_disabled}")
        except Exception as e:
            print(f"Error toggling sharpening file: {e}")
    
    def update_fps_config_ini(self, fps_limit):
        """Update the FPS config.ini file in mods/UnlockTheFps/ directory."""
        if not self.game_dir:
            return
        
        fps_config_path = os.path.join(self.game_dir, "mods", "UnlockTheFps", "config.ini")
        
        if not self.ensure_config_exists(fps_config_path):
            return
        
        try:
            
            # Write config file
            with open(fps_config_path, 'w') as f:
                f.write("[unlockthefps]\n")
                f.write(f"limit = {fps_limit}\n")
            
            print(f"Updated FPS config: {fps_limit}")
        except Exception as e:
            print(f"Error updating FPS config: {e}")

        except Exception as e:
            print(f"Error updating ERFPS FOV config: {e}")

    def ensure_config_exists(self, file_path):
        """Check if a config file exists. If not, warn the user and return False."""
        if not os.path.exists(file_path):
            filename = os.path.basename(file_path)
            message = self._t("config_missing_warning").format(file=filename)
            from tkinter import messagebox
            messagebox.showwarning(self._t("warning") if TRANSLATIONS[self.lang_var.get()].get("warning") else "Warning", message)
            print(f"Safety Check Failed: {file_path} is missing.")
            return False
        return True

    def add_language_selector(self, parent):
        lang_frame = ctk.CTkFrame(parent, fg_color="transparent")
        if parent == self.overlay:
             lang_frame.place(relx=1.0, rely=0.0, anchor="ne")
        else:
             lang_frame.pack(pady=5)
        
        current_display = "English"
        for code, name in LANGUAGES_LIST:
            if code == self.lang_var.get():
                current_display = name
                break
                
        lang_menu = ctk.CTkComboBox(lang_frame, 
                                     values=[n for c, n in LANGUAGES_LIST],
                                     command=self.on_lang_change,
                                     width=150, height=28,
                                     font=("Arial", 11),
                                     fg_color="#1a1a1a",
                                     button_color="#d4af37", button_hover_color="#b48f17")
        lang_menu.set(current_display)
        lang_menu.pack()

    def on_scaling_change(self, choice):
        """Handle UI scaling change."""
        scaling_map = {"100%": "1.0", "125%": "1.25", "150%": "1.5", "175%": "1.75", "200%": "2.0"}
        scaling_val = scaling_map.get(choice, "1.0")
        
        print(f"Changing UI scaling to: {choice} ({scaling_val})")
        self.save_config_value("ui_scaling", scaling_val)
        
        try:
            val = float(scaling_val)
            ctk.set_widget_scaling(val)
            ctk.set_window_scaling(val)
        except Exception as e:
            print(f"Error applying real-time scaling: {e}")

    def setup_chat_sidebar(self, parent):
        """Setup the UI for the Global Chat Sidebar."""
        
        # Reset color tags state since we are creating a fresh text widget
        if hasattr(self, 'created_color_tags'):
            del self.created_color_tags

        # Top Frame for Nickname
        nick_frame = ctk.CTkFrame(parent, fg_color="transparent")
        nick_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(nick_frame, text=self._t("chat_nickname_label"), font=("Arial", 11, "bold")).pack(side="top", anchor="w", padx=5)
        self.chat_nick_entry = tk.Entry(nick_frame, textvariable=self.chat_nickname_var,
                                        bg="#1a1a1a", fg="white", insertbackground="white", 
                                        relief="flat", font=("Arial", 12))
        self.chat_nick_entry.pack(fill="x", padx=5, pady=(2, 5), ipady=3)
        self.chat_nick_entry.bind("<FocusOut>", lambda e: self.save_config_value("chat_nickname", self.chat_nickname_var.get()))
        
        self.chat_status_label = ctk.CTkLabel(nick_frame, text=self._t("chat_disconnected"), font=("Arial", 10), text_color="gray")
        self.chat_status_label.pack(side="top", anchor="e", padx=10)

        # Chat History
        self.chat_history = ctk.CTkTextbox(parent, state="disabled", wrap="word", font=("Segoe UI Emoji", 11), fg_color="#0d0d0d")
        self.chat_history.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Request full history from server if we are reconnecting UI
        if self.chat_socket and hasattr(self, 'send_queue'):
            try:
                self.send_queue.put(json.dumps({"type": "request_history"}))
            except Exception as e:
                print(f"Error requesting history: {e}")
        
        # Bottom Frame for Input
        input_frame = ctk.CTkFrame(parent, fg_color="transparent")
        input_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        # Input field with Emoji button
        input_sub_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        input_sub_frame.pack(fill="x", pady=(0, 5))
        
        self.chat_input = tk.Entry(input_sub_frame, bg="#1a1a1a", fg="white", 
                                   insertbackground="white", font=("Segoe UI Emoji", 11),
                                   bd=1, relief="solid", highlightthickness=1, 
                                   highlightbackground="#d4af37", highlightcolor="#d4af37")
        self.chat_input.pack(side="left", fill="x", expand=True, padx=(0, 5), ipady=5) # ipady for height
        self.chat_input.bind("<Return>", lambda e: self.send_chat_message())
        self.chat_input.bind("<KeyRelease>", self.check_emoji_shortcuts)
        self.chat_input.bind("<BackSpace>", self.on_chat_backspace)
        
        # Emoji Picker logic (Hybrid: Built-in + System Hint)
        self.emoji_list = [
            "😀", "😂", "🤣", "😊", "😍", "🤔", "🙄", "📢", "⚔️", "🛡️", "🔥", "✨", 
            "💀", "👍", "👎", "🎉", "❤️", "💔", "🌟", "👀", "👋", "🙌", "👑", "💪",
            "⚡", "🎮", "🗡️", "🏹", "🧪", "🧙", "👹", "🏆"
        ]
        self.emoji_btn = ctk.CTkButton(input_sub_frame, text="😀", width=35, height=35, 
                                       fg_color="#1a1a1a", border_width=1, border_color="#d4af37",
                                       command=self.show_emoji_menu)
        self.emoji_btn.pack(side="right")
        
        self.chat_send_btn = ctk.CTkButton(input_frame, text=self._t("chat_send_btn"), height=35, 
                                           command=self.send_chat_message, fg_color="#3e4a3d", hover_color="#4e5b4d")
        self.chat_send_btn.pack(fill="x")
        
        self.chat_count_label = ctk.CTkLabel(input_frame, text="", font=("Arial", 10), text_color="#aaaaaa")
        self.chat_count_label.pack(side="top", pady=(5, 0))
        
        # Start connection process if not already running
        if not self.chat_thread or not self.chat_thread.is_alive():
            self.connect_chat()
        
        # If already connected (e.g. after language refresh), update UI immediately
        elif self.chat_socket:
             self.chat_status_label.configure(text=self._t("chat_connected"), text_color="green")
             if hasattr(self, 'online_count'):
                 self.chat_count_label.configure(text=self._t("chat_online_count").format(count=self.online_count))
        
        if not hasattr(self, '_chat_polling_started'):
            self.receive_chat_messages()
            self._chat_polling_started = True

    def setup_about_tab(self):
        """Setup the content for the About tab with a side-by-side layout."""
        # Main container (no scroll unless window is very small)
        main_container = ctk.CTkFrame(self.tab_about, fg_color="transparent")
        main_container.pack(fill="both", expand=True, padx=10, pady=10)

        # Title at the very top
        ctk.CTkLabel(main_container, text=self._t("about_title"), font=("Cinzel", 26, "bold"), text_color="#d4af37").pack(pady=(0, 20))

        # Horizontal split frame
        split_frame = ctk.CTkFrame(main_container, fg_color="transparent")
        split_frame.pack(fill="both", expand=True)

        # --- Left Column: Who are we? ---
        left_col = ctk.CTkFrame(split_frame, fg_color="#1a1a1a", border_width=1, border_color="#d4af37")
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 10))

        ctk.CTkLabel(left_col, text=self._t("about_spp_title"), font=("Arial", 16, "bold"), text_color="#d4af37").pack(pady=(15, 10))
        
        desc_label = ctk.CTkLabel(left_col, text=self._t("about_spp_desc"), 
                                  font=("Arial", 12), text_color="#cccccc", 
                                  wraplength=280, justify="center")
        desc_label.pack(padx=15, pady=(0, 20), fill="both", expand=True)

        # --- Right Column: Support ---
        right_col = ctk.CTkFrame(split_frame, fg_color="#1a1a1a", border_width=1, border_color="#d4af37")
        right_col.pack(side="right", fill="both", expand=True, padx=(10, 0))

        ctk.CTkLabel(right_col, text=self._t("about_support_title"), font=("Arial", 16, "bold"), text_color="#d4af37").pack(pady=(15, 10))

        # Support Buttons
        btns_container = ctk.CTkFrame(right_col, fg_color="transparent")
        btns_container.pack(pady=5, expand=True)

        # Discord
        ctk.CTkButton(btns_container, text=f"💬 {self._t('about_discord')}", 
                      command=lambda: webbrowser.open("https://discord.gg/wYyXVTS9bz"),
                      fg_color="#5865F2", hover_color="#4752C4", width=180, height=38,
                      font=("Arial", 11, "bold")).pack(pady=8)

        # Patreon
        ctk.CTkButton(btns_container, text=f"❤️ {self._t('about_patreon')}", 
                      command=lambda: webbrowser.open("https://www.patreon.com/conan513"),
                      fg_color="#F96854", hover_color="#E05B48", width=180, height=38,
                      font=("Arial", 11, "bold")).pack(pady=8)

        # PayPal
        ctk.CTkButton(btns_container, text=f"💸 {self._t('about_paypal')}", 
                      command=lambda: webbrowser.open("https://www.paypal.com/donate/?hosted_button_id=3J7L23CSNBVUG"),
                      fg_color="#003087", hover_color="#00256B", width=180, height=38,
                      font=("Arial", 11, "bold")).pack(pady=8)

        # Version info at bottom
        version_text = f"ER Launcher v{getattr(self, 'VERSION', '1.0.0')}"
        ctk.CTkLabel(main_container, text=version_text, font=("Arial", 10), text_color="#666666").pack(side="bottom", pady=(10, 0))

    def show_emoji_menu(self):
        """Show a popup with built-in emojis and a hint for the system picker."""
        if hasattr(self, 'emoji_popup') and self.emoji_popup.winfo_exists():
            self.emoji_popup.destroy()
            return

        self.emoji_popup = ctk.CTkToplevel(self)
        self.emoji_popup.title("")
        self.emoji_popup.geometry("180x330")
        self.emoji_popup.attributes("-topmost", True)
        self.emoji_popup.resizable(False, False)
        self.emoji_popup.overrideredirect(True)
        
        # Position near the button
        x = self.emoji_btn.winfo_rootx() - 150
        y = self.emoji_btn.winfo_rooty() - 335
        self.emoji_popup.geometry(f"+{x}+{y}")
        
        frame = ctk.CTkFrame(self.emoji_popup, fg_color="#1a1a1a", border_width=1, border_color="#d4af37")
        frame.pack(fill="both", expand=True)

        # Quick Emojis
        inner_frame = ctk.CTkFrame(frame, fg_color="transparent")
        inner_frame.pack(padx=2, pady=5)
        
        for i, emoji in enumerate(self.emoji_list):
            btn = ctk.CTkButton(inner_frame, text=emoji, width=38, height=32, 
                                 fg_color="transparent", hover_color="#333333",
                                 font=("Segoe UI Emoji", 12),
                                 command=lambda e=emoji: self.add_emoji(e))
            btn.grid(row=i // 4, column=i % 4, padx=1, pady=1)

        # System Hint Button
        hint_btn = ctk.CTkButton(frame, text="Win + . (Full Selection)", font=("Segoe UI", 10, "bold"), height=28,
                                  fg_color="#2a2a2a", hover_color="#3a3a3a", border_width=1, border_color="#d4af37",
                                  command=lambda: [self.show_emoji_hint(), self.emoji_popup.destroy()])
        hint_btn.pack(fill="x", padx=10, pady=(5, 10))

    def show_emoji_hint(self):
        """Show a hint about the native Windows emoji picker and force focus."""
        from tkinter import messagebox
        messagebox.showinfo("Emoji", self._t("chat_emoji_hint"))
        self.chat_input.focus_set() # Force focus back to allow system picker to find it

    def add_emoji(self, emoji):
        """Insert emoji into chat input and return focus."""
        current = self.chat_input.get()
        self.chat_input.delete(0, "end")
        self.chat_input.insert(0, current + emoji)
        self.emoji_popup.destroy()
        self.chat_input.focus_set() # Crucial for system integration

    def check_emoji_shortcuts(self, event=None):
        """Check if the last typed characters match an emoji shortcut."""
        if not hasattr(self, 'chat_input') or not self.chat_input.winfo_exists():
            return

        # Get current text and cursor position
        text = self.chat_input.get()
        try:
            cursor_pos = self.chat_input.index(tk.INSERT)
        except:
            return
        
        # We only care about text up to the cursor
        current_text = text[:cursor_pos]
        
        # Iterate over shortcuts
        for shortcut, emoji in self.emoji_shortcuts.items():
            if current_text.endswith(shortcut):
                # Calculate start position of the shortcut
                start_pos = cursor_pos - len(shortcut)
                
                # Delete shortcut
                self.chat_input.delete(start_pos, cursor_pos)
                
                # Insert emoji
                self.chat_input.insert(start_pos, emoji)
                
                # Stop after one replacement to avoid conflicts
                return

    def on_chat_backspace(self, event):
        """Handle backspace to correctly delete surrogate pairs (emojis)."""
        if not hasattr(self, 'chat_input') or not self.chat_input.winfo_exists():
            return
            
        if self.chat_input.selection_present(): 
            return
        
        try:
            cursor_pos = self.chat_input.index(tk.INSERT)
            if cursor_pos == 0: return
            
            text = self.chat_input.get()
            current_tk_pos = 0
            
            for char in text:
                char_len = 2 if ord(char) > 0xFFFF else 1
                next_tk_pos = current_tk_pos + char_len
                
                if next_tk_pos == cursor_pos:
                    if char_len > 1:
                        self.chat_input.delete(current_tk_pos, next_tk_pos)
                        return "break"
                    return # Normal char, let default handle it
                
                current_tk_pos = next_tk_pos
        except Exception as e:
            print(f"Backspace error: {e}")

    def connect_chat(self):
        """Start the background thread for WebSocket connection."""
        if not self.chat_thread or not self.chat_thread.is_alive():
            self.chat_status_label.configure(text=self._t("chat_connecting"), text_color="orange")
            self.chat_thread = threading.Thread(target=self.chat_loop, daemon=True)
            self.chat_thread.start()

    def chat_loop(self):
        """Background loop to handle WebSocket communication."""
        self.send_queue = queue.Queue()

        async def run():
            uri = "ws://94.72.100.43:8765" # Public server
            try:
                async with websockets.connect(uri) as websocket:
                    self.chat_socket = websocket
                    self.chat_queue.put({"type": "status", "connected": True})
                    
                    # Create tasks for receiving and sending
                    async def receive():
                        try:
                            async for message in websocket:
                                try:
                                    data = json.loads(message)
                                    self.chat_queue.put(data)
                                except json.JSONDecodeError:
                                    pass
                        except Exception as e:
                            print(f"Receive error: {e}")
                    
                    async def send():
                        while True:
                            try:
                                while not self.send_queue.empty():
                                    payload = self.send_queue.get_nowait()
                                    await websocket.send(payload)
                            except queue.Empty:
                                pass
                            except Exception as e:
                                print(f"Send error: {e}")
                                break # Exit send loop if connection lost
                            await asyncio.sleep(0.1)
                    
                    # Wait for either to finish (usually receive finishes when socket closes)
                    await asyncio.gather(receive(), send())
                    
            except Exception as e:
                print(f"Chat connection error: {e}")
            finally:
                self.chat_socket = None
                self.chat_queue.put({"type": "status", "connected": False})

        asyncio.run(run())

    def send_chat_message(self):
        """Send a message from the input field to the server."""
        from tkinter import messagebox
        
        msg = self.chat_input.get().strip()
        nick = self.chat_nickname_var.get().strip()
        
        if not msg:
            return

        if len(msg) > 500:
            messagebox.showwarning("Warning", "Message is too long! (Max 500 characters)")
            return
        
        if not nick:
            messagebox.showwarning(self._t("warning") if TRANSLATIONS[self.lang_var.get()].get("warning") else "Warning", 
                                   self._t("chat_nick_required"))
            return

        if self.chat_socket:
            # Client-side Anti-spam (3s)
            now = time.time()
            if now - self.last_send_time < 3:
                self.chat_status_label.configure(text="Spam protection: 3s", text_color="red")
                self.after(2000, lambda: self.chat_status_label.configure(
                    text=self._t("chat_connected"), text_color="green") if self.chat_socket else None)
                return

            payload = json.dumps({
                "type": "chat", 
                "nickname": nick, 
                "message": msg,
                "user_id": self.chat_user_id
            }, ensure_ascii=False)
            if not hasattr(self, 'send_queue'):
                self.send_queue = queue.Queue()
            self.send_queue.put(payload)
            self.last_send_time = now # Update cooldown
            self.chat_input.delete(0, 'end')

    def receive_chat_messages(self):
        """Poll the chat queue and update the UI."""
        if not hasattr(self, 'online_count'):
            self.online_count = 0
            
        try:
            while True:
                try:
                    data = self.chat_queue.get_nowait()
                except queue.Empty:
                    break

                # Safety check: Ensure UI elements exist before updating
                if not hasattr(self, 'chat_history') or not self.chat_history.winfo_exists():
                    continue

                if data["type"] == "status":
                    if data["connected"]:
                        if self.chat_status_label.winfo_exists():
                            self.chat_status_label.configure(text=self._t("chat_connected"), text_color="green")
                        
                        # Show welcome message upon connection
                        if not hasattr(self, '_welcome_shown'):
                            self.chat_history.configure(state="normal")
                            self.chat_history.insert("end", f"{self._t('chat_welcome')}\n", "system")
                            self.chat_history.configure(state="disabled")
                            self._welcome_shown = True
                        
                        # Initial count update if we already have it
                        if self.chat_count_label.winfo_exists():
                            self.chat_count_label.configure(text=self._t("chat_online_count").format(count=self.online_count))
                    else:
                        if self.chat_status_label.winfo_exists():
                            self.chat_status_label.configure(text=self._t("chat_disconnected"), text_color="gray")
                        if self.chat_count_label.winfo_exists():
                            self.chat_count_label.configure(text="")
                        
                        # Try to reconnect after a delay
                        self.after(5000, self.connect_chat)
                
                elif data["type"] == "user_count":
                    self.online_count = data.get("count", 0)
                    if self.chat_count_label.winfo_exists():
                        self.chat_count_label.configure(text=self._t("chat_online_count").format(count=self.online_count))
                
                elif data["type"] == "history":
                    self.chat_history.configure(state="normal")
                    self.chat_history.delete("1.0", "end")
                    for entry in data.get("messages", []):
                        self._add_to_history_ui(entry)
                    self.chat_history.configure(state="disabled")
                
                elif data["type"] == "chat":
                    self.chat_history.configure(state="normal")
                    self._add_to_history_ui(data)
                    self.chat_history.configure(state="disabled")
                
                elif data["type"] == "system":
                    self.chat_history.configure(state="normal")
                    self._add_to_history_ui(data)
                    self.chat_history.configure(state="disabled")

        except Exception as e:
            # Log error but don't stop the loop (e.g., if widget destroyed during update)
            # print(f"Chat UI polling error: {e}")
            pass
        
        # Poll again soon
        self.after(100, self.receive_chat_messages)

    def _add_to_history_ui(self, data):
        """Helper to add a single message to the text box."""
        msg_type = data.get("type", "chat")
        time_str = data.get("time", datetime.now().strftime("%H:%M"))
        
        if not hasattr(self, 'created_color_tags'):
            self.created_color_tags = set()
            self.chat_history.tag_config("time", foreground="gray")
            self.chat_history.tag_config("system", foreground="#888888")
            self.chat_history.tag_config("tripcode", foreground="#555555")
            # Tags are now ready
        
        if msg_type == "system":
            sys_msg = data.get("message", "")
            nick = data.get("nickname", "User")
            text = self._t(f"chat_{sys_msg}").format(nickname=nick)
            self.chat_history.insert("end", f"[{time_str}] {text}\n", "system")
        else:
            nick = data.get("nickname", "Unknown")
            msg = data.get("message", "")
            color = data.get("color", "#d4af37") # Fallback to gold
            
            # Unique tag name for this color
            tag_name = f"color_{color.replace('#', '')}"
            
            if tag_name not in self.created_color_tags:
                self.chat_history.tag_config(tag_name, foreground=color)
                self.created_color_tags.add(tag_name)
            
            tripcode = data.get("tripcode", "")
            
            self.chat_history.insert("end", f"[{time_str}] ", "time")
            self.chat_history.insert("end", f"{nick}", tag_name)
            if tripcode:
                self.chat_history.insert("end", f"({tripcode})", "tripcode")
            self.chat_history.insert("end", ": ", tag_name)
            self.chat_history.insert("end", f"{msg}\n", "msg")
        
        
        self.chat_history.see("end")
        
        # Optimization: Prune old messages if they exceed 200 lines
        try:
            line_count = int(self.chat_history.index("end-1c").split(".")[0])
            if line_count > 200:
                # Delete first 50 lines to keep it smooth
                self.chat_history.delete("1.0", "51.0")
                self.chat_history.insert("1.0", "... (older messages pruned for performance) ...\n", "system")
        except Exception as e:
            print(f"Optimization error: {e}")

    def monitor_process(self):
        try:
            is_running = self.is_game_running()
            
            # Update lockdown status globally
            self.set_lockdown(is_running)
            
            if is_running:
                self.update_status(self._t("now_running"), "#44ff44")
                self.game_active = True
                self.launch_start_time = 0 # Reset on successful launch
            else:
                if hasattr(self, 'game_active') and self.game_active:
                    self.game_active = False

                # Status Reset Logic:
                # If we are in "Launching" state (launch_start_time > 0)
                if self.launch_start_time > 0:
                    # If it's been more than 30 seconds, give up and reset
                    if time.time() - self.launch_start_time > 30:
                        self.launch_start_time = 0
                        self.update_status(self._t("ready"), "gray")
                    # Otherwise, stay in "Launching" state (do nothing, don't reset to Ready)
                else:
                    # Normal state, ensure it says Ready
                    self.update_status(self._t("ready"), "gray")
        except Exception as e:
            print(f"[ERROR] monitor_process exception: {e}")
        
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
            output = subprocess.check_output('tasklist /FI "IMAGENAME eq eldenring.exe" /NH', shell=True).decode('utf-8', errors='ignore')
            return "eldenring.exe" in output.lower()
        except:
            return False

    def get_game_pid(self):
        """Find the PID of eldenring.exe, prioritizing our own game_process."""
        try:
            if hasattr(self, 'game_process') and self.game_process:
                if self.game_process.poll() is None:
                    return self.game_process.pid

            output = subprocess.check_output('tasklist /FI "IMAGENAME eq eldenring.exe" /NH /FO CSV', shell=True).decode('utf-8', errors='ignore')
            if "eldenring.exe" in output.lower():
                import csv
                reader = csv.reader(io.StringIO(output))
                for row in reader:
                    if row and row[0].lower() == "eldenring.exe":
                        return int(row[1])
        except Exception as e:
            pass
        return None

    def on_modpack_change(self, value):
        # Map translated value back to internal key
        internal_key = "Vanilla"
        if value == self._t("qol"): internal_key = "Quality of Life"
        elif value == self._t("diablo"): internal_key = "Diablo Loot (RNG)"
        
        self.save_config_value("modpack", internal_key)
        self.update_status(f"{self._t('mod_label')} {value}")
        self.update_save_converter_state()
        
        # Handle Mod Settings tab visibility
        if internal_key in ["Quality of Life", "Diablo Loot (RNG)"]:
            # Show Mod Settings tab if not already present
            if not hasattr(self, 'tab_mod_settings') or self.tab_mod_settings not in self.tabview._tab_dict.values():
                self.create_mod_settings_tab()
            else:
                # Tab already exists, just update Map checkbox state
                self.update_map_checkbox_state()
        else:
            # Hide Mod Settings tab if present
            if hasattr(self, 'tab_mod_settings'):
                try:
                    self.tabview.delete(self._t("tab_mod_settings"))
                    delattr(self, 'tab_mod_settings')
                except:
                    pass
        
        if self.game_dir and not self.is_game_running():
            self.apply_modpack(internal_key)
            
        # Sync settings regardless of whether we applied the modpack (e.g. if game running)
        self.sync_modpack_settings()

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
            
            # Sync UI settings with the new modpack state
            self.sync_modpack_settings()
            
        except Exception as e:
            print(f"Error applying modpack: {e}")

    def sync_modpack_settings(self):
        """Sync UI settings with actual file state of the selected modpack."""
        if not self.game_dir:
            return

        # Get current selected value (translated)
        current_val = self.modpack_var.get()
        
        # Determine internal key
        internal_key = "Vanilla"
        if current_val == self._t("qol"): internal_key = "Quality of Life"
        elif current_val == self._t("diablo"): internal_key = "Diablo Loot (RNG)"
        elif current_val == "Quality of Life": internal_key = "Quality of Life" # Handle internal key if set directly
        elif current_val == "Diablo Loot (RNG)": internal_key = "Diablo Loot (RNG)"

        # Determine current mod folder based on internal key
        pack_map = {
            "Quality of Life": "mod_qol",
            "Diablo Loot (RNG)": "mod_rng"
        }
        mod_folder = pack_map.get(internal_key)
        
        # Only apply to QoL and Diablo modpacks
        if not mod_folder:
            return
            
        # Check Sharpening Status
        shader_file = os.path.join(self.game_dir, mod_folder, "shader", "gxposteffect.shaderbnd.dcx")
        shader_disabled = shader_file + ".disabled"
        
        # If .disabled exists, sharpening is ENABLED (checkbox unchecked)
        # If .dcx exists, sharpening is DISABLED (checkbox checked)
        if os.path.exists(shader_disabled):
            self.disable_sharpening_var.set(False)
            self.save_config_value("disable_sharpening", "False")
        elif os.path.exists(shader_file):
            self.disable_sharpening_var.set(True)
            self.save_config_value("disable_sharpening", "True")
            
        # Sync FPS Unlocker Status (Global)
        fps_dll = os.path.join(self.game_dir, "dinput8.dll")
        fps_disabled = fps_dll + ".disabled"
        
        if os.path.exists(fps_dll):
            self.qol_fps_unlocker_var.set(True)
            self.save_config_value("qol_fps_unlocker_enabled", "True")
            self.update_fps_limit_visibility()
        elif os.path.exists(fps_disabled):
            self.qol_fps_unlocker_var.set(False)
            self.save_config_value("qol_fps_unlocker_enabled", "False")
            self.update_fps_limit_visibility()
        else:
             # Default to unchecked (enabled) if neither exists, or maybe check warning?
             # For sync, we just want to reflect state if possible.
             pass

    def get_mod_config(self, pack_name):
        """Build mod config dynamically based on toggle states and pack name."""
        # Base DLLs always enabled
        dlls = ["ersc.dll", "Scripts-Data-Exposer-FS.dll", "waygate_client.dll"]
        
        # Add optional DLLs based on toggles
        if self.qol_questlog_var.get():
            dlls.append("erquestlog.dll")
        # er_alt_saves.dll is now mandatory for modpacks
        dlls.append("er_alt_saves.dll")
        
        # Build DLL string
        dll_str = '["' + '", "'.join(dlls) + '"]'
        
        # Determine mod folder based on pack name
        if pack_name == "Quality of Life":
            mod_folder = "mod_qol"
        elif pack_name == "Diablo Loot (RNG)":
            mod_folder = "mod_rng"
        else:
            mod_folder = "modpack"  # fallback
        
        # Build mod config
        mod_enabled = "true" if self.qol_map_var.get() else "false"
        mods_str = f'[{{ enabled = {mod_enabled}, name = "{mod_folder}", path = "{mod_folder}" }}]'
        
        return {
            "dlls": dll_str,
            "mods": mods_str
        }

    def update_toml_config(self, game_path, pack_name):
        toml_path = os.path.join(game_path, "config_eldenring.toml")
        if not self.ensure_config_exists(toml_path):
            return

        # Define configurations
        configs = {
            "Vanilla": {
                "dlls": '["ersc.dll", "Scripts-Data-Exposer-FS.dll", "waygate_client.dll"]',
                "mods": '[{ enabled = false, name = "modpack", path = "modpack" }]'
            },
            "Quality of Life": self.get_mod_config("Quality of Life"),
            "Diablo Loot (RNG)": self.get_mod_config("Diablo Loot (RNG)")
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
            return fallback
        except:
            return fallback


    def update_save_converter_state(self):
        """Restore save converter state (enabled for all modes including Vanilla)."""
        current_mod = self.modpack_var.get()
        saved_val = self.read_config_value("auto_save_converter", "0")
        self.conv_var.set(saved_val)
        self.conv_checkbox.configure(state="normal", text_color="#d4af37")

    def handle_save_conversion(self, mode):
        """Rename all save files (ER0000-ER0009, .mod, and .bak) between .sl2 and .co2 extensions."""
        if self.read_config_value("auto_save_converter", "0") != "1":
            return True

        save_folder = self.get_steam_id64()
        if not save_folder or not os.path.exists(save_folder):
            self.update_status(self._t("save_folder_not_found"), "#ff4444")
            return False

        self.update_status(self._t("converting_saves"), "#d4af37")
        
        try:
            files = os.listdir(save_folder)
            count = 0
            
            for f in files:
                old_path = os.path.join(save_folder, f)
                f_lower = f.lower()
                
                if not f_lower.startswith("er000"):
                    continue
                
                new_f = None
                if mode == "seamless":
                    # Standard: .sl2 -> .co2
                    if f_lower.endswith(".sl2"):
                        new_f = f[:-4] + ".co2"
                    # Alternative: .mod -> .mod.co2
                    elif f_lower.endswith(".mod"):
                        new_f = f + ".co2"
                    # .bak versions
                    elif f_lower.endswith(".sl2.bak"):
                        new_f = f.replace(".sl2.bak", ".co2.bak")
                else: # online
                    # Standard: .co2 -> .sl2
                    if f_lower.endswith(".co2") and not f_lower.endswith(".mod.co2"):
                        new_f = f[:-4] + ".sl2"
                    # Alternative: .mod.co2 -> .mod
                    elif f_lower.endswith(".mod.co2"):
                        new_f = f[:-4]
                    # .bak versions
                    elif f_lower.endswith(".co2.bak"):
                        new_f = f.replace(".co2.bak", ".sl2.bak")

                if new_f:
                    new_path = os.path.join(save_folder, new_f)
                    if os.path.exists(new_path):
                        os.remove(new_path)
                    os.rename(old_path, new_path)
                    count += 1
            
            if count > 0:
                print(f"Converted {count} save files for {mode} mode.")
            return True
        except Exception as e:
            self.update_status(f"Save conversion error: {e}", "#ff4444")
            return False


    def launch_seamless(self):
        if self.is_game_running():
            self.update_status(self._t("running"), "#ff4444")
            return

        # Ensure modpack is applied before launch
        self.apply_modpack(self.modpack_var.get())
        if not self.save_password(): return
        if not self.handle_save_conversion("seamless"): return
        if not self.toggle_dlls("seamless"): return
        if os.path.exists(self.launch_exe):
            self.update_status(self._t("launch_seamless"), "#d4af37")
            subprocess.Popen([self.launch_exe], cwd=self.game_dir)
            self.launch_start_time = time.time()
            
        else:
            self.update_status(self._t("exe_not_found"), "#ff4444")

    def launch_online(self):
        if self.is_game_running():
            self.update_status(self._t("running"), "#ff4444")
            return
            
        # Ensure modpack is applied before launch (though Online usually needs Vanilla)
        self.apply_modpack(self.modpack_var.get())
        if not self.handle_save_conversion("online"): return
        if not self.toggle_dlls("online"): return
        if os.path.exists(self.launch_exe):
            self.update_status(self._t("launch_online"), "#d4af37")
            subprocess.Popen([self.launch_exe], cwd=self.game_dir)
            self.launch_start_time = time.time()

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

    def set_lockdown(self, locked):
        """Show or hide the lockdown overlay when the game is running."""
        if locked:
            if not self.lockdown_frame:
                # Create frame on the main window (self) to cover everything
                self.lockdown_frame = ctk.CTkFrame(self, fg_color="#0f0f0f", corner_radius=0)
                self.lockdown_status = ctk.CTkLabel(self.lockdown_frame, text=self._t("lockdown_message"), 
                                                   font=("Cinzel", 18, "bold"), text_color="#d4af37", wraplength=400)
                self.lockdown_status.place(relx=0.5, rely=0.5, anchor="center")
            
            self.lockdown_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.lockdown_frame.lift() # Ensure it's on top
        else:
            if self.lockdown_frame:
                self.lockdown_frame.place_forget()

    def check_for_updates(self):
        """Check for updates in a background thread."""
        def check():
            try:
                # Fetch remote version
                with urllib.request.urlopen(self.VERSION_URL) as response:
                    remote_version = response.read().decode('utf-8').strip()
                
                print(f"Local Version: {self.VERSION}, Remote Version: {remote_version}")
                
                if remote_version != self.VERSION:
                    self.after(0, lambda: self.show_update_available(remote_version))
                    
            except Exception as e:
                print(f"Update check failed: {e}")

        threading.Thread(target=check, daemon=True).start()

    def show_update_available(self, new_version):
        """Show the update button in the UI."""
        if hasattr(self, 'update_btn'):
            self.update_btn.configure(text=self._t("update_available_btn"))
            
            # Pack into the footer (above status label)
            # Since status_label is packed side="bottom", packing update_btn side="top" or "bottom" works.
            # Let's pack it to the TOP of the footer, pushing status label down?
            # Or just pack it. Since status_label is already packed, packing update_btn will place it...
            # Wait, if we use pack(side="top"), it goes to the top of footer.
            try:
                self.update_btn.pack(side="top", pady=(0, 5))
            except:
                pass
            
            # Flash effect or highlight
            self.update_btn.configure(fg_color="#e15f41", hover_color="#c44569")

    def perform_update(self):
        """Download new version and restart using a batch script."""
        try:
            print("Downloading update...")
            self.update_btn.configure(text="Downloading...", state="disabled")
            
            # dynamic update name
            new_exe = "ER_Launcher_new.exe"
            urllib.request.urlretrieve(self.UPDATE_URL, new_exe)
            
            print("Download complete. Preparing update script...")
            
            # Create update batch script
            bat_script = """
@echo off
timeout /t 3 /nobreak > nul
del "ER_Launcher.exe"
move "ER_Launcher_new.exe" "ER_Launcher.exe"
set _MEIPASS2=
set PYTHONPATH=
start "" "ER_Launcher.exe"
del "%~f0"
"""
            with open("update.bat", "w") as f:
                f.write(bat_script)
                
            # Launch script and exit safely
            # Use CREATE_NEW_CONSOLE to ensure it lives on
            subprocess.Popen("update.bat", shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
            
            # Use os._exit to bypass cleanup handlers that might crash
            self.after(100, lambda: os._exit(0))
            
        except Exception as e:
            print(f"Update failed: {e}")
            self.update_btn.configure(text="Update Failed!", fg_color="red")
            self.after(3000, lambda: self.update_btn.configure(text=f"Update Available!", state="normal"))

if __name__ == "__main__":
    app = EldenRingLauncher()
    app.mainloop()
