"""
Plugin system for Koda.

Discovers and loads plugins from the plugins/ directory.
Each plugin is a Python file that can define hook functions:

    PLUGIN_NAME = "My Plugin"          # Required — display name
    PLUGIN_VERSION = "1.0"             # Optional

    def on_load(config):               # Called when plugin is loaded
    def on_unload():                   # Called when plugin is unloaded
    def process_text(text, config):    # Post-process text after Koda's pipeline. Return modified text.
    def get_commands():                # Return list of (regex_pattern, action_fn, description)
    def get_menu_items():              # Return list of (label, callback)

Plugins are loaded alphabetically. Place a file in plugins/ and restart Koda.
"""

import importlib.util
import logging
import os

logger = logging.getLogger("koda.plugins")

PLUGINS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugins")


class PluginManager:
    """Discovers, loads, and manages Koda plugins."""

    def __init__(self):
        self._plugins = {}  # name → module

    def discover_and_load(self, config=None):
        """Scan plugins/ directory and load all .py plugin files."""
        if not os.path.isdir(PLUGINS_DIR):
            return

        for filename in sorted(os.listdir(PLUGINS_DIR)):
            if not filename.endswith(".py") or filename.startswith("_"):
                continue

            filepath = os.path.join(PLUGINS_DIR, filename)
            module_name = f"koda_plugin_{filename[:-3]}"

            try:
                spec = importlib.util.spec_from_file_location(module_name, filepath)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)

                name = getattr(mod, "PLUGIN_NAME", filename[:-3])
                version = getattr(mod, "PLUGIN_VERSION", "?")

                # Call on_load hook
                if hasattr(mod, "on_load"):
                    mod.on_load(config or {})

                self._plugins[name] = mod
                logger.info("Loaded plugin: %s v%s (%s)", name, version, filename)

            except Exception as e:
                logger.error("Failed to load plugin %s: %s", filename, e)

    def unload_all(self):
        """Unload all plugins, calling on_unload hooks."""
        for name, mod in self._plugins.items():
            try:
                if hasattr(mod, "on_unload"):
                    mod.on_unload()
            except Exception as e:
                logger.error("Error unloading plugin %s: %s", name, e)
        self._plugins.clear()

    @property
    def loaded(self):
        """Return dict of loaded plugin names → modules."""
        return dict(self._plugins)

    # --- Hook dispatch ---

    def run_text_processors(self, text, config):
        """Run all plugin text processors on the text. Returns modified text."""
        for name, mod in self._plugins.items():
            if hasattr(mod, "process_text"):
                try:
                    result = mod.process_text(text, config)
                    if result is not None:
                        text = result
                except Exception as e:
                    logger.error("Plugin %s process_text error: %s", name, e)
        return text

    def get_all_commands(self):
        """Collect voice commands from all plugins.

        Returns list of (pattern, action_fn, description).
        """
        commands = []
        for name, mod in self._plugins.items():
            if hasattr(mod, "get_commands"):
                try:
                    cmds = mod.get_commands()
                    if cmds:
                        commands.extend(cmds)
                except Exception as e:
                    logger.error("Plugin %s get_commands error: %s", name, e)
        return commands

    def get_all_menu_items(self):
        """Collect tray menu items from all plugins.

        Returns list of (label, callback).
        """
        items = []
        for name, mod in self._plugins.items():
            if hasattr(mod, "get_menu_items"):
                try:
                    menu = mod.get_menu_items()
                    if menu:
                        items.extend(menu)
                except Exception as e:
                    logger.error("Plugin %s get_menu_items error: %s", name, e)
        return items
