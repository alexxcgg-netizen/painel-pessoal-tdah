import os

def get_chrome_path():
    linux_paths = [
        "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
        "/opt/pw-browsers/chromium"
    ]
    for path in linux_paths:
        if os.path.exists(path):
            return path
    return None
