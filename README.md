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

```
ultra-meter/
├─ ultra_meter.py         # Main application script
├─ assets/
│  ├─ app.ico             # App/tray icon
│  ├─ upload.png          # Upload arrow icon
│  ├─ download.png        # Download arrow icon
│  ├─ pin_on.png          # (Optional) Pin active icon
│  └─ pin_off.png         # (Optional) Pin inactive icon
└─ build/
   └─ UltraMeter.iss      # Inno Setup script (optional installer)
```

---

## 🚀 Running from Source

1. Install Python **3.10+** on Windows.
2. Install dependencies:
   ```bash
   pip install pyqt6 psutil pywin32
   ```
3. Run UltraMeter:
   ```bash
   python ultra_meter.py
   ```

---

## 📦 Building a Standalone EXE (no Python required)

Requires **[PyInstaller](https://pyinstaller.org/)**.

```bash
pip install pyinstaller pyqt6 psutil pywin32

pyinstaller --noconfirm --onefile --windowed ^
  --name UltraMeter ^
  --icon assets\app.ico ^
  --add-data "assets;assets" ^
  ultra_meter.py
```

Output:
```
dist/UltraMeter.exe
```
This EXE can run on any Windows PC without Python installed.

---

## 🛠 Creating a Windows Installer (Optional)

Requires **[Inno Setup](https://jrsoftware.org/isinfo.php)**.

1. Build the EXE (make sure `dist/UltraMeter.exe` exists).
2. Edit `build/UltraMeter.iss` to match your paths.
3. Compile with Inno Setup:
   ```bash
   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" build\UltraMeter.iss
   ```
4. Distribute the generated `UltraMeter-Setup.exe`.

Installer will:
- Copy UltraMeter to `C:\Program Files\UltraMeter\`
- Create Start Menu & optional Desktop shortcuts
- Register an uninstaller
- Optionally launch UltraMeter after install

---

## 🖱 Usage

- 📌 **Pin/Unpin:** Click pin icon or tray → "Pin/Unpin"
- 🖱 **Drag:** Unpin, move to desired position, re-pin
- 📍 **Dock to right corner:** Tray → "Dock to right corner"
- 📏 **Toggle units:** Tray → "Units: bits / bytes" or `Ctrl+Shift+U`
- 🖥 **Start with Windows:** Tray → "Start with Windows"
- 👁 **Show/Hide:** Double-click tray icon
- ❌ **Quit:** Tray → "Quit"

---

## 🗑 Uninstall

- **If installed via installer:**
  - Control Panel → "Uninstall a program" → UltraMeter
  - Uninstaller will stop UltraMeter, remove autostart, and delete settings in `%APPDATA%\UltraMeter`
- **If using portable EXE:**
  - Quit from tray → delete EXE
  - Disable autostart from tray before deletion

---

## 📄 License

Licensed under the [MIT License](LICENSE).

---

## 📷 Screenshots

*(Optional — add your widget & tray screenshots here)*

![Widget Example](docs/widget-example.png)
![Tray Menu](docs/tray-menu.png)

---

### 💡 Notes

- Anti-virus may warn about unsigned EXEs. For distribution, consider [code-signing](https://learn.microsoft.com/en-us/windows/win32/seccrypto/code-signing).
- If you replace icons in `assets/`, re-build with PyInstaller to embed them.

---

### ❤️ Contributing

Pull requests and feature suggestions are welcome.  
If you find UltraMeter useful, consider giving the repo a ⭐ on GitHub!
