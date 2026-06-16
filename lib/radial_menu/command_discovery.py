# -*- coding: utf-8 -*-
"""pyRevit command discovery module.

Discovers pyRevit commands from the active session and filesystem,
parses command hierarchy (extension/tab/pulldown), and builds
filtered hierarchical tree structures for WPF TreeView binding.
"""

import os
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Graceful imports for .NET / pyRevit dependencies
# ---------------------------------------------------------------------------
try:
    from System.Collections.ObjectModel import ObservableCollection
    _HAS_CLR = True
except ImportError:
    _HAS_CLR = False
    ObservableCollection = None

# Module-level command cache
_cached_commands = None


def _safe_str(obj):
    """Safely convert any object to a unicode string."""
    try:
        return u"{}".format(obj)
    except Exception:
        return u"<non-printable>"


# =========================================================================
# TreeItem — lightweight data node for WPF TreeView binding
# =========================================================================

class TreeItem(object):
    """Hierarchical data item for WPF TreeView binding.

    Uses CLR-property-style accessors (PascalCase) so that WPF XAML
    data-binding can resolve ``{Binding Name}``, ``{Binding Children}``, etc.

    Args:
        name:        Display name of the node.
        is_command:  True if this node represents an executable command.
        icon_path:   Absolute path to the command icon image (optional).
        unique_id:   Unique command identifier string (optional).
        extension:   Extension name the command belongs to (optional).
        is_expanded: Whether the node should be expanded by default.
    """

    def __init__(self, name, is_command=False, icon_path=None,
                 unique_id=None, extension=None, is_expanded=False):
        self._name = name
        self._is_command = is_command
        self._icon_path = icon_path
        self._unique_id = unique_id
        self._extension = extension
        self._is_expanded = is_expanded
        if _HAS_CLR:
            self._children = ObservableCollection[object]()
        else:
            self._children = []

    # -- WPF-bound properties (PascalCase) ----------------------------------

    @property
    def Name(self):
        """str: Display name of this tree node."""
        return self._name

    @Name.setter
    def Name(self, value):
        self._name = value

    @property
    def IsCommand(self):
        """bool: True if this node represents an executable command."""
        return self._is_command

    @property
    def IconPath(self):
        """str or None: Absolute path to the icon image."""
        return self._icon_path

    @property
    def UniqueId(self):
        """str or None: Unique command identifier."""
        return self._unique_id

    @property
    def Extension(self):
        """str or None: Extension name the command belongs to."""
        return self._extension

    @property
    def IsExpanded(self):
        """bool: Whether this node is expanded in the tree."""
        return self._is_expanded

    @IsExpanded.setter
    def IsExpanded(self, value):
        self._is_expanded = value

    @property
    def Children(self):
        """ObservableCollection or list: Child nodes."""
        return self._children


# =========================================================================
# Bundle / hierarchy helpers
# =========================================================================

# Standard pyRevit bundle suffixes used to strip directory names
_BUNDLE_SUFFIXES = [
    ".extension", ".tab", ".panel", ".pulldown", ".splitbutton",
    ".pushbutton", ".linkbutton", ".smartbutton", ".urlbutton",
    ".contentbutton", ".colorbutton", ".togglebutton",
]


def get_bundle_title(dir_path):
    """Read the display title for a pyRevit bundle directory.

    Looks for a ``bundle.yaml`` file and extracts the ``title:`` field.
    Falls back to the directory name with the bundle suffix stripped.

    Args:
        dir_path: Absolute path to a bundle directory.

    Returns:
        str: Human-readable bundle title.
    """
    bundle_yaml = os.path.join(dir_path, "bundle.yaml")
    if os.path.exists(bundle_yaml):
        try:
            with open(bundle_yaml, "rb") as f:
                for line in f:
                    line = line.strip().decode("utf-8", "ignore")
                    if line.startswith("title:"):
                        title = (line.replace("title:", "")
                                 .replace("'", "")
                                 .replace('"', '')
                                 .strip())
                        if title:
                            return title
        except Exception:
            pass

    dir_name = os.path.basename(dir_path)
    for suffix in _BUNDLE_SUFFIXES:
        if dir_name.lower().endswith(suffix):
            dir_name = dir_name[:-len(suffix)]
            break
    return dir_name


def parse_command_hierarchy(cmd):
    """Extract the extension/tab/pulldown hierarchy from a command object.

    Parses the command's ``script`` path to determine which extension, tab,
    and pulldown/splitbutton the command lives under.

    Args:
        cmd: A pyRevit command object (must have a ``.script`` attribute).

    Returns:
        tuple: ``(extension_name, tab_name, pulldown_name)`` where
        *pulldown_name* may be ``None``.
    """
    script_path = getattr(cmd, "script", None)
    if not script_path:
        return u"External", u"Commands", None

    norm_path = os.path.normpath(script_path)
    parts = norm_path.split(os.path.sep)

    # Find where the extension starts
    ext_idx = -1
    for idx, part in enumerate(parts):
        if part.lower().endswith(".extension"):
            ext_idx = idx
            break

    if ext_idx != -1:
        ext_path = os.path.sep.join(parts[:ext_idx + 1])
        ext_name = get_bundle_title(ext_path)

        tab_name = u"Commands"
        pulldown_name = None

        tab_idx = -1
        for idx in range(ext_idx + 1, len(parts)):
            if parts[idx].lower().endswith(".tab"):
                tab_idx = idx
                tab_path = os.path.sep.join(parts[:tab_idx + 1])
                tab_name = get_bundle_title(tab_path)
                break

        if tab_idx != -1:
            for idx in range(tab_idx + 1, len(parts) - 1):
                part_lower = parts[idx].lower()
                if (part_lower.endswith(".pulldown")
                        or part_lower.endswith(".splitbutton")):
                    pd_path = os.path.sep.join(parts[:idx + 1])
                    pulldown_name = get_bundle_title(pd_path)
                    break

        return ext_name, tab_name, pulldown_name
    else:
        ext_name = getattr(cmd, "extension", None) or u"External"
        return ext_name, u"Commands", None


def find_extension_dirs():
    """Scan the filesystem for all pyRevit ``.extension`` directories.

    Collects extension root directories from:
    1. ``pyRevit_config.ini`` user extensions list
    2. ``pyrevit.userconfig.get_ext_root_dirs()``
    3. The default ``<HOME_DIR>/extensions`` folder
    4. The parent of the current extension directory

    Returns:
        list[str]: De-duplicated list of absolute paths to ``.extension``
        directories.
    """
    roots = []

    # 1. Custom user extensions from config
    try:
        appdata = os.environ.get("APPDATA")
        if appdata:
            config_file = os.path.join(appdata, "pyRevit", "pyRevit_config.ini")
            if os.path.exists(config_file):
                with open(config_file, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("userextensions ="):
                            import json as _json
                            json_str = line.split("=", 1)[1].strip()
                            custom_paths = _json.loads(json_str)
                            if isinstance(custom_paths, list):
                                roots.extend(custom_paths)
                            break
    except Exception as e:
        logger.debug(u"Failed to parse config file: %s", _safe_str(e))

    # 2. Standard ext root dirs via pyRevit API
    try:
        from pyrevit import userconfig
        roots.extend(userconfig.get_ext_root_dirs())
    except Exception:
        pass

    # 3. Default extension directory
    try:
        from pyrevit import HOME_DIR
        default_ext_dir = os.path.join(HOME_DIR, "extensions")
        if os.path.exists(default_ext_dir):
            roots.append(default_ext_dir)
    except Exception:
        pass

    # 4. Current extension directory
    try:
        cur_ext_dir = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "../../../../"))
        if os.path.exists(cur_ext_dir):
            roots.append(os.path.dirname(cur_ext_dir))
    except Exception:
        pass

    # De-duplicate and normalise
    unique_roots = list(set(
        os.path.normpath(r) for r in roots if r and os.path.exists(r)
    ))
    logger.debug(u"Resolved extension roots for scanning: %s", unique_roots)

    # Find all *.extension directories (up to two levels deep)
    ext_dirs = []
    for root in unique_roots:
        if root.lower().endswith(".extension"):
            ext_dirs.append(root)
        else:
            try:
                for name in os.listdir(root):
                    p = os.path.join(root, name)
                    if os.path.isdir(p):
                        if name.lower().endswith(".extension"):
                            ext_dirs.append(p)
                        else:
                            try:
                                for subname in os.listdir(p):
                                    subp = os.path.join(p, subname)
                                    if (os.path.isdir(subp)
                                            and subname.lower().endswith(
                                                ".extension")):
                                        ext_dirs.append(subp)
                            except Exception:
                                pass
            except Exception as e:
                logger.debug(u"Failed to list directory %s: %s",
                             root, _safe_str(e))

    return list(set(ext_dirs))


# =========================================================================
# CommandDiscovery — wraps discovery + tree building logic
# =========================================================================

class _MockCommand(object):
    """Lightweight stand-in for pyRevit command objects discovered on disk."""

    def __init__(self, name, unique_id, extension, script_path):
        self.name = name
        self.title = name
        self.bundle = name
        self.unique_id = unique_id
        self.extension = extension
        self.script = script_path


class CommandDiscovery(object):
    """Discovers pyRevit commands and builds hierarchical tree structures.

    Combines the pyRevit session API (``sessionmgr.find_all_commands``)
    with a filesystem fallback that scans ``.extension`` directories for
    button bundles that may not be loaded in the current session.

    Args:
        clean_id_func: Optional callable ``(str) -> str`` used to normalise
            path-segment strings into id parts.  Falls back to a simple
            lower-case alphanumeric strip if not provided.
        icon_resolver: Optional callable ``(str) -> str`` that resolves a
            raw icon path to the correct themed variant.  Defaults to
            identity (pass-through) if not provided.
    """

    # pyRevit button bundle suffixes
    _BUTTON_SUFFIXES = (
        ".pushbutton", ".smartbutton", ".linkbutton", ".urlbutton",
        ".contentbutton", ".colorbutton", ".togglebutton",
    )
    # Broader suffix list for id cleaning
    _ALL_SUFFIXES = list(_BUNDLE_SUFFIXES) + [
        ".pushbutton", ".smartbutton", ".linkbutton", ".urlbutton",
        ".contentbutton", ".colorbutton", ".togglebutton",
    ]

    def __init__(self, clean_id_func=None, icon_resolver=None):
        self._clean_id = clean_id_func or self._default_clean_id
        self._resolve_icon = icon_resolver or (lambda p: p)

    @staticmethod
    def _default_clean_id(name):
        """Strip non-alphanumeric characters and lower-case a name."""
        import re
        return re.sub(r'[^a-zA-Z0-9_]', '', name).lower()

    # -----------------------------------------------------------------
    # Command discovery
    # -----------------------------------------------------------------

    def find_all_commands(self):
        """Discover all available pyRevit commands.

        First attempts to load commands from the active pyRevit session via
        ``sessionmgr.find_all_commands``.  Then performs a filesystem scan
        of all known ``.extension`` directories to pick up commands that
        may not be loaded in the current session.

        Results are cached globally so that repeated calls are free.

        Returns:
            list: Command objects (real pyRevit or ``_MockCommand``).
        """
        global _cached_commands
        if _cached_commands is not None:
            logger.debug(u"Returning cached pyRevit commands.")
            return _cached_commands

        logger.debug(u"Loading active pyRevit commands safely...")
        cmds = []
        unique_ids = set()

        # 1. Try to load from sessionmgr
        try:
            from pyrevit.loader import sessionmgr
            all_cmds = sessionmgr.find_all_commands(cache=True)
            logger.debug(u"Found %d commands via sessionmgr.", len(all_cmds))
            for cmd in all_cmds:
                uid = getattr(cmd, "unique_id", None)
                if uid:
                    cmds.append(cmd)
                    unique_ids.add(uid.lower())
        except Exception as ex:
            logger.debug(u"Default find_all_commands failed (%s).",
                         _safe_str(ex))

        # 2. Filesystem scan to discover missing commands
        ext_dirs = []
        try:
            ext_dirs = find_extension_dirs()
            logger.debug(u"Scanning extension directories: %s", ext_dirs)
        except Exception as e_exts:
            logger.debug(u"Failed to find extension directories: %s",
                         _safe_str(e_exts))

        for ext_dir in ext_dirs:
            try:
                ext_name = get_bundle_title(ext_dir)
                self._scan_extension_dir(
                    ext_dir, ext_name, cmds, unique_ids)
            except Exception as e_scan:
                logger.debug(u"Filesystem scan failed for ext %s: %s",
                             ext_dir, _safe_str(e_scan))

        logger.debug(u"Total resolved commands: %d", len(cmds))
        _cached_commands = cmds
        return cmds

    def _scan_extension_dir(self, ext_dir, ext_name, cmds, unique_ids):
        """Walk an extension directory and add any missing button commands."""
        for dirpath, dirnames, _filenames in os.walk(ext_dir):
            if ".git" in dirpath or "bin" in dirpath or "obj" in dirpath:
                continue

            for dirname in list(dirnames):
                lower_dir = dirname.lower()
                is_btn = any(
                    lower_dir.endswith(s) for s in self._BUTTON_SUFFIXES)
                if not is_btn:
                    continue

                button_dir = os.path.join(dirpath, dirname)
                script_file = os.path.join(button_dir, "script.py")
                bundle_yaml = os.path.join(button_dir, "bundle.yaml")

                # A valid button must have either script.py or bundle.yaml
                if not os.path.exists(script_file) and \
                        not os.path.exists(bundle_yaml):
                    continue

                parent_dir = os.path.dirname(ext_dir)
                rel_path = button_dir.replace(parent_dir, "").strip(os.path.sep)
                parts = rel_path.split(os.path.sep)

                clean_parts = []
                for p in parts:
                    stripped = p
                    for suffix in self._ALL_SUFFIXES:
                        if p.lower().endswith(suffix):
                            stripped = p[:-len(suffix)]
                            break
                    clean_parts.append(self._clean_id(stripped))

                unique_id = "_".join(clean_parts)

                # Skip the RadialMenu toggle button itself
                if unique_id == "radialmenu_radialmenu_radialmenu_toggleradialmenu":
                    continue
                if unique_id.lower() in unique_ids:
                    continue

                real_name = get_bundle_title(button_dir)
                script = script_file if os.path.exists(script_file) \
                    else button_dir

                cmds.append(_MockCommand(
                    real_name, unique_id, ext_name, script))
                unique_ids.add(unique_id.lower())
                logger.debug(u"Filesystem scan added missing command: "
                             u"%s (%s)", real_name, unique_id)

    # -----------------------------------------------------------------
    # Tree building
    # -----------------------------------------------------------------

    def build_command_tree(self, commands, query=None):
        """Build a filtered hierarchical tree of commands.

        Parses every command's hierarchy, applies an optional text filter,
        and returns a nested structure of :class:`TreeItem` nodes grouped
        by *extension → tab → pulldown*.

        Args:
            commands: Iterable of command objects (as returned by
                :meth:`find_all_commands`).
            query:    Optional search string.  Only commands whose title,
                extension, tab, or pulldown name contain *query*
                (case-insensitive) are included.

        Returns:
            list[TreeItem] or ObservableCollection: Root-level tree nodes.
                Returns an ``ObservableCollection[object]`` when CLR is
                available, otherwise a plain list.
        """
        if query:
            query = query.lower().strip()

        # Step 1: Parse and filter
        parsed = self._parse_commands(commands)
        filtered = self._filter_parsed(parsed, query)

        # Step 2: Group into hierarchy
        tree_data = {}
        for cmd in filtered:
            ext = cmd["ext_name"]
            tab = cmd["tab_name"]
            pd = cmd["pulldown_name"]

            tree_data.setdefault(ext, {})
            tree_data[ext].setdefault(tab, {})
            tree_data[ext][tab].setdefault(pd, [])
            tree_data[ext][tab][pd].append(cmd)

        # Step 3: Build TreeItem hierarchy
        if _HAS_CLR:
            root_collection = ObservableCollection[object]()
            add_fn = root_collection.Add
        else:
            root_collection = []
            add_fn = root_collection.append

        for ext_name in sorted(tree_data.keys()):
            should_expand = bool(query)
            ext_item = TreeItem(ext_name, is_command=False,
                                is_expanded=should_expand)
            add_fn(ext_item)

            tabs = tree_data[ext_name]
            for tab_name in sorted(tabs.keys()):
                tab_item = TreeItem(tab_name, is_command=False,
                                    is_expanded=should_expand)
                ext_item.Children.Add(tab_item) if _HAS_CLR \
                    else ext_item.Children.append(tab_item)

                pulldowns = tabs[tab_name]
                # Pulldown folders first
                sorted_pd_names = sorted(
                    k for k in pulldowns.keys() if k is not None)
                for pd_name in sorted_pd_names:
                    pd_item = TreeItem(pd_name, is_command=False,
                                       is_expanded=should_expand)
                    if _HAS_CLR:
                        tab_item.Children.Add(pd_item)
                    else:
                        tab_item.Children.append(pd_item)

                    cmds_in_pd = sorted(
                        pulldowns[pd_name], key=lambda x: x["title"])
                    for c_info in cmds_in_pd:
                        c_item = TreeItem(
                            name=c_info["title"],
                            is_command=True,
                            icon_path=c_info["icon_path"],
                            unique_id=c_info["unique_id"],
                            extension=c_info["ext_name"],
                        )
                        if _HAS_CLR:
                            pd_item.Children.Add(c_item)
                        else:
                            pd_item.Children.append(c_item)

                # Direct commands under tab (no pulldown)
                if None in pulldowns:
                    direct_cmds = sorted(
                        pulldowns[None], key=lambda x: x["title"])
                    for c_info in direct_cmds:
                        c_item = TreeItem(
                            name=c_info["title"],
                            is_command=True,
                            icon_path=c_info["icon_path"],
                            unique_id=c_info["unique_id"],
                            extension=c_info["ext_name"],
                        )
                        if _HAS_CLR:
                            tab_item.Children.Add(c_item)
                        else:
                            tab_item.Children.append(c_item)

        return root_collection

    # -----------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------

    def _parse_commands(self, commands):
        """Parse raw command objects into flat dicts with hierarchy info."""
        parsed_list = []
        for cmd in commands:
            uid = getattr(cmd, "unique_id", None)
            if not uid:
                continue
            if uid == "radialmenu_radialmenu_radialmenu_toggleradialmenu":
                continue

            title = (getattr(cmd, "title", None)
                     or getattr(cmd, "name", None)
                     or getattr(cmd, "bundle", None)
                     or u"Unknown Command")

            icon_path = None
            script_path = getattr(cmd, "script", None)
            if script_path:
                dir_path = os.path.dirname(script_path)
                for name in ["icon.png", "icon32.png", "icon16.png"]:
                    p = os.path.join(dir_path, name)
                    if os.path.exists(p):
                        icon_path = p
                        break

            ext_name, tab_name, pulldown_name = parse_command_hierarchy(cmd)

            parsed_list.append({
                "title": title,
                "unique_id": uid,
                "icon_path": self._resolve_icon(icon_path),
                "ext_name": ext_name,
                "tab_name": tab_name,
                "pulldown_name": pulldown_name,
            })
        return parsed_list

    @staticmethod
    def _filter_parsed(parsed, query):
        """Filter parsed command dicts by a search query string."""
        if not query:
            return parsed
        filtered = []
        for cmd in parsed:
            match = (query in cmd["title"].lower()
                     or query in cmd["ext_name"].lower()
                     or query in cmd["tab_name"].lower()
                     or (cmd["pulldown_name"]
                         and query in cmd["pulldown_name"].lower()))
            if match:
                filtered.append(cmd)
        return filtered
