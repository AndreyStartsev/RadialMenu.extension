# RadialMenu.extension

A customizable, context-aware **Radial Menu Extension for Autodesk Revit** built on top of the **pyRevit** framework.

This extension provides Revit professionals with an efficient, heads-up radial context menu that displays relevant commands depending on the active view type, selection state, and Revit element category/class. It eliminates repetitive ribbon navigation and significantly accelerates drafting and modeling workflows.

---

## ✨ Features

- **Context-Aware Dynamic Commands**: Displays tailored command sectors depending on:
  - **Active View Types** (3D Views, Plan Views, Section Views, Sheets).
  - **Selection Context** (Empty canvas, pre-highlighted elements, active selection sets).
  - **Revit Category & Class Filtering** (e.g. Wall, Floor, Pipe, Duct, FamilyInstance).
- **Flexible 3-Level Hierarchy**: Support for 1 to 10 sectors per level, recursively organizing commands and submenus.
- **Interactive Visual Customizer**: An interactive modeless customizer dialog to manage commands, drag-and-drop to reorder, and configure context rules per command.
- **Alternative Visual Styles**:
  - *Standard Petals*: Smooth segmented arc sectors.
  - *Circle Petals*: Petals rendered as clean geometric circles.
- **Smooth Animations**:
  - *Fade In*: Graceful opacity fade.
  - *Pop Out*: Scale-up from the center with easing curves.
  - *Fan Out*: Unfolding rotation and scale sweep.
- **Hardware-Accelerated WPF Rendering**: Built-in GPU `BitmapCache` acceleration for smooth 60 FPS transitions inside Autodesk Revit.

---

## 🛠️ Installation

1. Ensure **[pyRevit](https://github.com/eirannejad/pyRevit)** is installed and attached to your Revit version (supports Revit 2020 through 2026+).
2. Clone this repository into your pyRevit extensions directory (or any custom search path):
   ```bash
   git clone https://github.com/AndreyStartsev/RadialMenu.extension.git
   ```
3. If using a custom path, add the parent directory to your pyRevit extension search paths:
   ```bash
   pyrevit extend ui RadialMenu "C:\path\to\parent_directory"
   ```
4. Reload pyRevit in Revit (**pyRevit ➔ Reload**) or run `pyrevit reload` in your terminal.

---

## 🚀 How to Use

1. **Activate the Menu**: Click the **Radial Menu** button in the Revit ribbon (under the **RadialMenu** tab).
2. **Open / Hover**: Press and hold the **Right Mouse Button (RMB)** anywhere in the Revit canvas for **400 ms** (customizable) to bring up the radial menu.
3. **Execute Commands**: Hover over any petal/circle and release the mouse to trigger the command, or click on a sub-level sector to drill down.
4. **Customize**: Click the **Gear (⚙️)** in the center of the menu to open the Customizer panel, where you can modify the command pool, reorder petals, and configure context rules.

---

## 🏗️ Architecture & File Structure

```files
RadialMenu.extension/
├── README.md                           # Project documentation
├── .gitignore                          # Git ignore rules
├── lib/
│   └── radial_menu/
│       ├── core.py                     # Core logic and WPF window implementation
│       └── win32_hook.py               # Win32 low-level mouse hook manager
└── RadialMenu.tab/
    └── RadialMenu.panel/
        └── ToggleRadialMenu.pushbutton/
            ├── icon.png                # Ribbon button icon
            ├── bundle.yaml             # pyRevit pushbutton metadata
            ├── script.py               # Main Python execution backend & mouse hook
            ├── ui.xaml                 # WPF markup for the Radial Menu & Customizer
            └── radial_menu_config.json # Default configuration & command pool
```

---

## ⚙️ Configuration Format

User layout, commands, and rules are saved in `radial_menu_config.json`:

```json
{
  "settings": {
    "hold_delay_ms": 400,
    "trigger_mode": "hold",
    "use_circles": false,
    "animation_style": "fade",
    "theme": "pyRevit Dark",
    "color_scheme": "auto"
  },
  "command_pool": [
    {
      "id": "zoom_fit",
      "type": "built_in",
      "name": "Zoom Fit",
      "command": "zoom",
      "icon": "🔍",
      "level": 1,
      "parent": null,
      "priority": 10,
      "context_rules": {}
    }
  ]
}
```

---

## 🤝 Contributing

Contributions and feedback are welcome! Please feel free to open an issue or submit a pull request.

---

## 📄 License

MIT License.
