import PyInstaller.__main__
import os

# Create the EXE using PyInstaller
PyInstaller.__main__.run([
    'launcher.py',
    '--onefile',
    '--noconsole',
    '--name=ER_Launcher',
    '--icon=app_icon.ico',
    '--add-data=background.png;.',
    '--add-data=app_icon.ico;.',
    '--add-data=app_icon.png;.',
    '--clean',
])
