# RadialMenu.extension

A highly customizable, context-aware **Radial Menu Extension for Autodesk Revit** built on top of the **pyRevit** framework.

This extension provides Revit professionals with an efficient, heads-up, radial context menu that displays relevant commands depending on the active view type, selection state, and Revit element category/class. It eliminates repetitive ribbon navigation and speeds up drafting and modeling workflows.

---

## ✨ Features

- **Context-Aware Dynamic Commands**: Displays tailored command sectors depending on:
  - **Active View Types** (3D Views, Plan Views, Sheets).
  - **Selection Context** (Pre-highlighted elements, active selection sets).
  - **Revit Category & Class Filtering** (e.g. Wall, Floor, Pipe, Duct).
- **Flexible 3-Level Hierarchy**: Support for 1 to 10 sectors per level, recursively promoting submenus when parent commands are inactive.
- **Visual Command Customizer**: An interactive modeless customizer dialog to manage commands, assign icons/emojis, drag-and-drop to reorder, and configure context rules per command.
- **Alternative Visual Styles**:
  - *Standard Petals*: Smooth segmented arc sectors.
  - *Circle Petals*: Petals rendered as perfect geometric circles.
- **Professional Transitions**:
  - *Fade In*: Graceful opacity fade.
  - *Pop Out*: Scale-up from the center with easing curves.
  - *Fan Out*: Unfolding rotation and scale sweep.
- **Hardware-Accelerated WPF Rendering**: Built-in GPU `BitmapCache` acceleration for stutter-free 60 FPS transitions inside Autodesk Revit.

---

## 📸 Interface Preview

*(We would love to showcase the menu in action here!)*

| Normal Style (Petals) | Alternative Style (Circles) | Customizer Panel |
| :---: | :---: | :---: |
| ![Radial Menu Petals](docs/images/menu_petals.png) | ![Radial Menu Circles](docs/images/menu_circles.png) | ![Customizer Dialog](docs/images/customizer.png) |

> [!TIP]
> **Contributors**: Please replace the placeholders in the `docs/images/` folder with actual screenshots to finalize this section.

---

## 🛠️ Installation

1. Ensure **[pyRevit](https://github.com/eirannejad/pyRevit)** is installed and attached to your Revit version.
2. Clone this repository into your pyRevit extensions directory (or any custom search path):
   ```bash
   git clone https://github.com/AndreyStartsev/RadialMenu.extension.git
   ```
3. If using a custom path, add the parent folder to your pyRevit extension search paths:
   ```bash
   pyrevit extend ui RadialMenu "C:\path\to\parent_folder"
   ```
4. Reload Revit or run `pyrevit reload` in the terminal to load the extension.

---

## 🚀 How to Use

1. **Activate the Menu**: Click the **Toggle Radial Menu** button in the Revit ribbon (under the **SKREP** or **RadialMenu** tab).
2. **Open / Hover**: Press and hold the **Right Mouse Button (RMB)** anywhere in the Revit canvas for **400 ms** (default, customizable) to bring up the menu.
3. **Execute Commands**: Hover over any petal/circle and release the mouse to trigger the command, or click on a sub-level sector to drill down.
4. **Customize**: Click **Gear (⚙️)** in the center of the menu to open the Customizer panel, where you can modify the command pool and rules.

---

## 🏗️ Architecture & File Structure

```files
RadialMenu.extension/
├── README.md                           # Project documentation (this file)
├── .gitignore                          # Git ignore definitions
├── lib/
│   └── radial_menu/
│       └── config_manager.py           # Configuration read/write utilities
└── RadialMenu.tab/
    └── RadialMenu.panel/
        └── ToggleRadialMenu.pushbutton/
            ├── icon.png                # Ribbon button icon
            ├── script.py               # Main Python execution backend & mouse hook
            ├── ui.xaml                 # WPF markup for the Radial Menu & Customizer
            └── RadialMenu_debug.log    # Runtime execution log file
```

---

## ⚙️ Configuration Format

User layout, commands, and rules are saved in `RadialMenu_config.json` inside the user directory.

```json
{
  "settings": {
    "hold_delay": 400,
    "animation_style": "fan",
    "use_circles": true,
    "l1_max_angle": 360,
    "l2_max_angle": 90,
    "l3_max_angle": 90
  },
  "command_pool": [
    {
      "id": "cmd_wall",
      "name": "Draw Wall",
      "emoji": "🧱",
      "command": "Revit.Create.Wall",
      "level": 1,
      "parent_id": null,
      "is_active": true,
      "context_rules": {
        "views": ["3D", "Plan"],
        "selection_mode": "none",
        "classes": []
      }
    }
  ]
}
```

---

## 🤝 Contributing

Contributions are welcome! Please open an issue or submit a pull request if you have ideas for improvements, new animations, or performance tweaks.
