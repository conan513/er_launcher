from launcher import EldenRingLauncher
import threading
import time

def check_state(app):
    time.sleep(3) # Wait for animation
    print(f"Window State: {app.state()}")
    print(f"Window Alpha: {app.attributes('-alpha')}")
    print(f"Window Visible: {app.winfo_viewable()}")
    app.quit()

app = EldenRingLauncher()
threading.Thread(target=check_state, args=(app,), daemon=True).start()
app.mainloop()
