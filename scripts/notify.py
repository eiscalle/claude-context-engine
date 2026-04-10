"""
Non-blocking Windows notification helper.

Uses VBScript WScript.Shell.Popup for zero-dependency toast-style notifications
that auto-dismiss after a timeout. Falls back to print() on non-Windows platforms.

Usage:
    from notify import notify
    notify("Context Engine", "Flush done: $0.02 | Today: $0.45")
"""

from __future__ import annotations

import logging
import subprocess
import sys
import tempfile
from pathlib import Path


def notify(title: str, message: str, timeout_seconds: int = 5) -> None:
    """Fire a non-blocking notification that auto-dismisses.

    On Windows: VBScript Popup (auto-dismiss after timeout_seconds).
    On other platforms: print to stdout (visible in manual runs, no-op in background).
    """
    if sys.platform != "win32":
        print(f"[{title}] {message}")
        return

    try:
        _notify_windows(title, message, timeout_seconds)
    except Exception as e:
        logging.debug("Notification failed (non-fatal): %s", e)


def _notify_windows(title: str, message: str, timeout: int) -> None:
    """Fire a VBScript Popup notification on Windows."""
    # Escape quotes for VBScript string literals
    safe_msg = message.replace('"', '""')
    safe_title = title.replace('"', '""')

    # 64 = vbInformation icon
    vbs_content = (
        f'WScript.CreateObject("WScript.Shell").Popup '
        f'"{safe_msg}", {timeout}, "{safe_title}", 64'
    )

    # Write to a temp file (auto-cleaned by OS)
    vbs_file = Path(tempfile.gettempdir()) / "claude_context_engine_notify.vbs"
    vbs_file.write_text(vbs_content, encoding="utf-8")

    # Spawn wscript.exe detached — returns immediately, popup auto-dismisses
    subprocess.Popen(
        ["wscript.exe", str(vbs_file)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
