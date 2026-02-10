import subprocess

# Test the exact same logic as is_game_running()
try:
    output = subprocess.check_output('tasklist /FI "IMAGENAME eq eldenring.exe" /NH', shell=True).decode('utf-8', errors='ignore')
    print("Raw output:")
    print(repr(output))
    print("\nLowercase output:")
    print(repr(output.lower()))
    print("\nContains 'eldenring.exe'?", "eldenring.exe" in output.lower())
except Exception as e:
    print(f"Error: {e}")
