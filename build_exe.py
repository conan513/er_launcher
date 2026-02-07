import PyInstaller.__main__
import os
import sys

def build():
    print("Starting build process for Elden Ring Launcher...")
    
    # Check if the target EXE is running
    target_exe = os.path.join("dist", "ER_Launcher.exe")
    if os.path.exists(target_exe):
        try:
            with open(target_exe, 'rb+') as f:
                pass
        except IOError:
            print("Error: 'ER_Launcher.exe' is currently running or locked.")
            print("Please close the launcher before building.")
            return

    # Ensure dependencies are available (basic check)
    try:
        import customtkinter
        import PIL
    except ImportError:
        print("Error: Required dependencies (customtkinter, Pillow) not found.")
        print("Please run: pip install -r requirements.txt")
        return

    # Assets to include
    assets = [
        ('background.png', '.'),
        ('app_icon.ico', '.'),
        ('app_icon.png', '.')
    ]

    params = [
        'launcher.py',
        '--onefile',
        '--noconsole',
        '--name=ER_Launcher',
        '--icon=app_icon.ico',
        '--clean',
    ]

    for src, dest in assets:
        if os.path.exists(src):
            params.append(f'--add-data={src};{dest}')
        else:
            print(f"Warning: Asset {src} not found, skipping.")

    print(f"Running PyInstaller with params: {params}")
    PyInstaller.__main__.run(params)
    print("Build complete! Check the 'dist' folder.")

if __name__ == "__main__":
    build()
