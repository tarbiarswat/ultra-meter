# 🖥️ UltraMeter

[![Made with Python](https://img.shields.io/badge/Made%20with-Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![PyQt6 GUI](https://img.shields.io/badge/GUI-PyQt6-41CD52?style=for-the-badge&logo=qt&logoColor=white)](https://www.riverbankcomputing.com/software/pyqt/intro)
[![Windows Only](https://img.shields.io/badge/OS-Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)](https://www.microsoft.com/windows)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)

> ⚡ **UltraMeter** — A lightweight, real-time internet speed meter widget for Windows that sits by your taskbar.  
> Displays upload/download speed dynamically in **KB/s**, **MB/s**, or **B/s** — auto-scaling units. No bloat, just speed.

---

## ✨ Features

- 📊 **Real-time** upload & download speed monitoring (auto unit scaling)
- 📍 **Docked by default** at the right corner of the taskbar
- 🖱 **Drag & pin** anywhere on screen
- 🪟 **Always on top** & minimal footprint
- 🖼 **Customizable icons** for app, upload, and download
- 📂 **Persistent settings** — remembers position, pin state, and units
- 🛠 **System tray menu** for:
  - Show/Hide meter
  - Pin/Unpin
  - Dock to right corner
  - Switch units (bits / bytes)
  - Toggle "Start with Windows"
  - Quit
- 💾 **Installer support** for easy deployment with Start Menu/Desktop shortcuts

---

## 📦 Folder Structure
ultra-meter/
├─ ultra_meter.py # Main application script
├─ assets/
│ ├─ app.ico # App/tray icon
│ ├─ upload.png # Upload arrow icon
│ ├─ download.png # Download arrow icon
│ ├─ pin_on.png # (Optional) Pin active icon
│ └─ pin_off.png # (Optional) Pin inactive icon
└─ build/
└─ UltraMeter.iss # Inno Setup script (optional installer)


---

## 🚀 Running from Source

1. Install Python **3.10+** on Windows.
2. Install dependencies:
   ```bash
   pip install pyqt6 psutil pywin32

3. Run UltraMeter:
    python ultra_meter.py

