"""Writes icon.ico for the exe (same artwork as the tray icon)."""
from overlay import tray_image

img = tray_image()
img.save("icon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
print("wrote icon.ico")
