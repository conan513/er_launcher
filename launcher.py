import os
import sys
import subprocess
import configparser
import customtkinter as ctk
from PIL import Image, ImageFilter, ImageEnhance

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
        self.geometry("600x500")
        self.resizable(False, False)
        self.attributes("-alpha", 0.0) # Start transparent
        
        # Set Window Icon
        self.icon_path = resource_path("app_icon.ico")
        if os.path.exists(self.icon_path):
            self.after(200, lambda: self.iconbitmap(self.icon_path))
        
        # Set theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Paths logic for Game folder
        if getattr(sys, 'frozen', False):
            self.launcher_base = os.path.dirname(sys.executable)
        else:
            self.launcher_base = os.path.dirname(os.path.abspath(__file__))
            
        self.game_dir = os.path.join(self.launcher_base, "Game")
        if not os.path.exists(self.game_dir):
            self.game_dir = self.launcher_base

        self.settings_path = os.path.join(self.game_dir, "ersc_settings.ini")
        self.launch_exe = os.path.join(self.game_dir, "EldenRing_Launcher.exe")

        # Background Image
        self.bg_image_path = resource_path("background.png")
        if os.path.exists(self.bg_image_path):
            # Main background
            bg_pil = Image.open(self.bg_image_path)
            self.bg_image = ctk.CTkImage(light_image=bg_pil,
                                         dark_image=bg_pil,
                                         size=(600, 500))
            self.bg_label = ctk.CTkLabel(self, image=self.bg_image, text="")
            self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)

        # Main Overlay Frame (Dark charcoal with subtle transparency)
        self.overlay = ctk.CTkFrame(self, fg_color="#151515", 
                                    bg_color="transparent", corner_radius=15,
                                    border_width=1, border_color="#d4af37")
        self.overlay.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.85, relheight=0.85)

        # UI Components inside overlay
        self.label = ctk.CTkLabel(self.overlay, text="ELDEN RING", font=("Cinzel", 36, "bold"), text_color="#d4af37")
        self.label.pack(pady=(25, 5))

        self.sub_label = ctk.CTkLabel(self.overlay, text="SINGLE PLAYER PROJECT: ELDEN RING LAUNCHER", font=("Arial", 11, "bold", "italic"), text_color="#c0c0c0")
        self.sub_label.pack(pady=(0, 20))

        # Password Frame
        self.pass_frame = ctk.CTkFrame(self.overlay, fg_color="transparent")
        self.pass_frame.pack(pady=10, padx=30, fill="x")

        self.pass_label = ctk.CTkLabel(self.pass_frame, text="Seamless Co-op Password:", font=("Arial", 13, "bold"), text_color="#d4af37")
        self.pass_label.pack(side="left", padx=(0, 10))

        self.password_var = ctk.StringVar(value=self.read_password())
        self.password_var.trace_add("write", self.on_password_change)
        self.password_entry = ctk.CTkEntry(self.pass_frame, textvariable=self.password_var, 
                                           width=200, height=35,
                                           fg_color="#1a1a1a", border_color="#d4af37",
                                           text_color="white")
        self.password_entry.pack(side="right", expand=True, fill="x")

        self.pass_note = ctk.CTkLabel(self.overlay, text="Password must be the same for all friends.\nOnly affects Seamless mode.", 
                                      font=("Arial", 10), text_color="#888888")
        self.pass_note.pack(pady=(0, 10))

        # Buttons
        self.button_frame = ctk.CTkFrame(self.overlay, fg_color="transparent")
        self.button_frame.pack(pady=15)

        # Seamless Column
        self.seamless_col = ctk.CTkFrame(self.button_frame, fg_color="transparent")
        self.seamless_col.pack(side="left", padx=15)

        self.seamless_btn = ctk.CTkButton(self.seamless_col, text="Seamless Co-op", 
                                          command=self.launch_seamless,
                                          height=50, width=200,
                                          font=("Arial", 15, "bold"),
                                          fg_color="#3e4a3d", hover_color="#4e5b4d",
                                          border_width=1, border_color="#d4af37",
                                          cursor="hand2")
        self.seamless_btn.pack()
        
        self.seamless_desc = ctk.CTkLabel(self.seamless_col, text="full coop experience with friends", 
                                          font=("Arial", 10), text_color="#aaaaaa")
        self.seamless_desc.pack(pady=(5, 0))

        # Online Column
        self.online_col = ctk.CTkFrame(self.button_frame, fg_color="transparent")
        self.online_col.pack(side="left", padx=15)

        self.online_btn = ctk.CTkButton(self.online_col, text="Online Mode", 
                                        command=self.launch_online,
                                        height=50, width=200,
                                        font=("Arial", 15, "bold"),
                                        fg_color="#1a1a1a", border_width=2, border_color="#d4af37",
                                        hover_color="#2a2a2a",
                                        cursor="hand2")
        self.online_btn.pack()

        self.online_desc = ctk.CTkLabel(self.online_col, text="original multiplayer experience", 
                                        font=("Arial", 10), text_color="#aaaaaa")
        self.online_desc.pack(pady=(5, 0))

        self.status_label = ctk.CTkLabel(self.overlay, text="", text_color="gray", font=("Arial", 11))
        self.status_label.pack(pady=10)

        # Fade in
        self.fade_in()
        
        # Start background monitor
        self.monitor_process()

    def monitor_process(self):
        if self.is_game_running():
            self.status_label.configure(text="Elden Ring is currently running", text_color="#44ff44")
        else:
            # If it was previously "Launching..." but game isn't running yet, keep it for a bit
            current_status = self.status_label.cget("text")
            if "Launching" not in current_status or "found" in current_status:
                self.status_label.configure(text="Ready to launch", text_color="gray")
        
        # Check every 2 seconds
        self.after(2000, self.monitor_process)

    def fade_in(self):
        alpha = self.attributes("-alpha")
        if alpha < 1.0:
            alpha += 0.05
            self.attributes("-alpha", alpha)
            self.after(20, self.fade_in)

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
                    self.status_label.configure(text="Settings saved.", text_color="#d4af37")
                return True
            else:
                self.status_label.configure(text="Settings file not found.", text_color="#ff4444")
                return False
        except Exception as e:
            self.status_label.configure(text=f"Error saving: {e}", text_color="#ff4444")
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
            self.status_label.configure(text=f"DLL Error: {e}", text_color="#ff4444")
            return False

    def is_game_running(self):
        try:
            # Check for eldenring.exe in the process list
            output = subprocess.check_output('tasklist /FI "IMAGENAME eq eldenring.exe" /NH', shell=True).decode('utf-8', errors='ignore')
            return "eldenring.exe" in output.lower()
        except:
            return False

    def launch_seamless(self):
        if self.is_game_running():
            self.status_label.configure(text="Elden Ring is already running!", text_color="#ff4444")
            return
        if not self.save_password(): return
        if not self.toggle_dlls("seamless"): return
        if os.path.exists(self.launch_exe):
            self.status_label.configure(text="Launching Seamless Co-op...", text_color="#d4af37")
            subprocess.Popen([self.launch_exe], cwd=self.game_dir)
        else:
            self.status_label.configure(text="Executable not found.", text_color="#ff4444")

    def launch_online(self):
        if self.is_game_running():
            self.status_label.configure(text="Elden Ring is already running!", text_color="#ff4444")
            return
        if not self.toggle_dlls("online"): return
        if os.path.exists(self.launch_exe):
            self.status_label.configure(text="Launching Online Mode...", text_color="#d4af37")
            subprocess.Popen([self.launch_exe], cwd=self.game_dir)
        else:
            self.status_label.configure(text="Executable not found.", text_color="#ff4444")

if __name__ == "__main__":
    app = EldenRingLauncher()
    app.mainloop()
