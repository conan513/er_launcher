---
description: how to build the standalone executable
---

### Quick Build (Windows)
Double-click `build.bat` in the root folder. It will automatically:
- Check for Python
- Install dependencies
- Run the build script
- Keep the terminal open to show results

### Manual Build
1. Ensure all dependencies are installed:
   ```powershell
   pip install -r requirements.txt
   ```

2. Run the build script:
   // turbo
   ```powershell
   python build_exe.py
   ```

3. The final executable will be located in the `dist` folder as `ER_Launcher.exe`.
