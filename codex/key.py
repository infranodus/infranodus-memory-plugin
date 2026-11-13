#!/usr/bin/env python3
"""The API key for clients that have no plugin settings (Codex, Grok Build).

Claude Code asks for the key in the plugin's settings and hands it to the
hooks itself, so hooks/memory.py reads it from nowhere else. Codex and Grok
Build have no such settings: this wrapper finds the key and then runs
hooks/memory.py with it, in the same process.

    key.py set-key KEY        store the key in ~/.infranodus/memory.json (mode 600)
    key.py clear-key          remove it
    key.py <memory.py action> [args]
                              hook-prompt, hook-flush, status, save, recall QUERY,
                              forget-last, optimize, dream, off, on: run that action
                              with the key from INFRANODUS_API_KEY, else the
                              stored one

This folder is not part of the plugin as Claude Code loads it.
"""

import os
import sys

HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
sys.path.insert(0, HOOKS)

import memory  # noqa: E402

KEY_VARIABLE = "CLAUDE_PLUGIN_OPTION_API_KEY"  # where memory.py expects it


def find_key():
    return memory._setting(os.environ.get("INFRANODUS_API_KEY")) or memory._setting(
        memory.load_settings().get("apiKey")
    )


def set_key(key):
    key = memory._setting(key)
    if not key:
        return "Usage: key.py set-key YOUR_INFRANODUS_API_KEY"
    settings = memory.load_settings()
    settings["apiKey"] = key
    settings.pop("apiBase", None)  # no longer used; INFRANODUS_API_BASE is for development
    memory.save_settings(settings)
    try:
        os.chmod(memory.settings_path(), 0o600)
    except OSError:
        pass
    return "InfraNodus API key stored in %s for Codex and Grok Build." % memory.settings_path()


def clear_key():
    settings = memory.load_settings()
    settings.pop("apiKey", None)
    settings.pop("apiBase", None)
    memory.save_settings(settings)
    return "Stored API key removed from %s." % memory.settings_path()


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "set-key":
        print(set_key(sys.argv[2] if len(sys.argv) > 2 else ""))  # the key is never printed
        return 0
    if action == "clear-key":
        print(clear_key())
        return 0
    if not memory.plugin_key():
        key = find_key()
        if key:
            os.environ[KEY_VARIABLE] = key
    return memory.main()


if __name__ == "__main__":
    sys.exit(main())
