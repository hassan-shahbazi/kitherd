#!/usr/bin/env python3
"""kitty kitten: pick a running herdr agent and re-open it in the current split.

The headless herdr server keeps panes and their agents alive with no UI, so a
Kitty view of an agent is only a window onto a pane that already runs. Closing
that window detaches; the pane keeps going. This kitten is the way back in: it
shows every agent on the default (headless) herdr session with its live status,
and re-attaches the one you choose.

Keys inside the panel:

    enter   attach the agent in the split the panel was opened from
    x       close its pane on the server (stops the agent) and stay in the list
    esc     leave, change nothing

The list refreshes about once a second. `herdr agent list` is one round trip
over the herdr socket, so the poll is cheap; fzf is only told to reload when the
rendered list really changed, which keeps the cursor still while you read.

`enter` types `herdr agent attach <pane>` into the split's own shell rather than
opening an overlay or a new window, so the attached pane takes over exactly the
split you were working in, and detaching drops you back at that shell prompt.
The split must be at a prompt for this to work.

Agents, not panes: herdr has no pane-level attach, and `agent attach` resolves
its target through the agent record, so a pane with no agent could only ever be
a dead row here. Every pane that runs an agent has a record either way — `herdr
agent start` requires a name, and herdr's own detector names a hand-started
agent after its kind.

Run standalone for the three helper modes the panel uses internally:
    herdr_panel.py --list          render the rows fzf shows
    herdr_panel.py --poll <port>   refresh loop, talks to fzf's --listen server
    herdr_panel.py --kill <pane>   close one pane on the server
"""

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

POLL_SECONDS = 1.0

# Import kitty modules only when running as a kitten
try:
    from kitty.boss import Boss

    RUNNING_AS_KITTEN = True
except ImportError:
    Boss = None
    RUNNING_AS_KITTEN = False


def _resolve(name: str) -> str:
    """Absolute path to `name`, resolved the way a shell would. kitty itself is
    started by launchd or desktop environments with a bare PATH, so kittens cannot rely on it."""
    found = shutil.which(name)
    if found:
        return found
    try:
        proc = subprocess.run(
            ["/bin/sh", "-lc", "command -v " + name],
            capture_output=True,
            text=True,
            timeout=10,
        )
        path = proc.stdout.strip()
        if proc.returncode == 0 and path:
            return path
    except (OSError, subprocess.SubprocessError):
        pass
    return name


HERDR = _resolve("herdr")
FZF = _resolve("fzf")
# sys.executable is the kitty binary inside a kitten, so the helper modes need a
# real interpreter resolved from PATH.
PYTHON = _resolve("python3")


def _self_path() -> str:
    """Absolute path of this file. kitty execs a kitten with no __file__ set, so
    fall back to the kitty configuration directory, where it is installed."""
    here = globals().get("__file__")
    if here and os.path.exists(here):
        return os.path.abspath(here)
    try:
        from kitty.constants import config_dir

        candidate = os.path.join(config_dir, "herdr_panel.py")
        if os.path.exists(candidate):
            return candidate
    except ImportError:
        pass
    found = shutil.which("herdr_panel.py")
    if found:
        return found
    return "herdr_panel.py"


SELF = _self_path()

# Colours per herdr AgentStatus (idle, working, blocked, done, unknown).
STATUS_COLOR = {
    "working": "33",  # yellow
    "blocked": "1;31",  # bold red
    "idle": "32",  # green
    "done": "34",  # blue
    "unknown": "90",  # grey
}


def _agents() -> Optional[List[Dict[str, Any]]]:
    """Every agent on the session in one socket round trip. None on failure,
    which is not the same as an empty fleet."""
    try:
        proc = subprocess.run(
            [HERDR, "agent", "list"], capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    try:
        return json.loads(proc.stdout)["result"]["agents"]
    except (ValueError, KeyError, TypeError):
        return None


def _pane_sort_key(pane: Dict[str, Any]) -> List[Any]:
    """Natural order for ids like w10:p2, which sort before w3:p2 as plain text.
    Pane counters are not decimal (w3:p8, w3:p9, w3:pA), so each part carries a
    type tag: two keys never compare an int against a str."""
    parts = re.split(r"(\d+)", pane.get("pane_id") or "")
    return [(0, int(part), "") if part.isdigit() else (1, 0, part) for part in parts]


def _home_relative(path: str) -> str:
    home = os.path.expanduser("~")
    if path == home:
        return "~"
    if path.startswith(home + os.sep):
        return "~" + path[len(home) :]
    return path


# Field 1 of every row is a pane id. This stands in that column when there is
# nothing to list, so the picker still opens and says why; it can never be a
# pane id, and enter and x both refuse it.
NO_TARGET = "-"


def render_rows() -> List[str]:
    """One line per agent. Field 1 is the pane id and carries no colour, so
    fzf's `{1}` placeholder gives a clean id whether or not --ansi strips. The
    pane id is also what `enter` attaches: an agent name is not always a usable
    target (two panes running claude are both named `claude`), but the pane id
    always resolves.

    An empty fleet renders as one explanatory row rather than an empty list, so
    the panel always shows the reason. It goes through the same reload path as
    everything else, so it is replaced the moment an agent appears."""
    agents = _agents()
    if agents is None:
        return [_note("the herdr server did not answer")]
    if not agents:
        return [_note("no agents are running yet — this list updates live")]

    rows = []
    for agent in sorted(agents, key=_pane_sort_key):
        status = agent.get("agent_status") or "unknown"
        rows.append(
            "{id}\t\033[{c}m{dot} {status}\033[0m\t\033[36m{agent}\033[0m"
            "\t\033[90m{cwd}\033[0m".format(
                id=(agent.get("pane_id") or "").ljust(8),
                c=STATUS_COLOR.get(status, "90"),
                dot="\u25cf",
                status=status.ljust(9),
                agent=(agent.get("agent") or "-").ljust(18),
                cwd=_home_relative(agent.get("cwd") or ""),
            )
        )
    return rows


def _note(text: str) -> str:
    return "{id}\t\033[90m{text}\033[0m".format(id=NO_TARGET.ljust(8), text=text)


def _is_pane_id(value: str) -> bool:
    """Pane ids look like w3:pF. The placeholder row never does."""
    return bool(value) and value != NO_TARGET and ":" in value


# --- helper modes, run as plain python3 from inside fzf -------------------


def mode_list() -> int:
    rows = render_rows()
    if rows:
        sys.stdout.write("\n".join(rows) + "\n")
    return 0


def mode_kill(pane_id: str) -> int:
    if not _is_pane_id(pane_id):
        return 0
    try:
        subprocess.run(
            [HERDR, "pane", "close", pane_id], capture_output=True, timeout=10
        )
    except (OSError, subprocess.SubprocessError):
        return 1
    return 0


def mode_poll(port: str) -> int:
    """Refresh fzf's list, but only when it changed. fzf resets the cursor on
    every reload, so an unconditional one-second reload would make the panel
    impossible to read. A GET each tick doubles as the liveness check: once fzf
    is gone the connection fails and this loop exits with it."""
    base = "http://127.0.0.1:%s" % port
    last = "\n".join(render_rows())
    while True:
        time.sleep(POLL_SECONDS)
        try:
            urllib.request.urlopen(base + "?limit=0", timeout=5).read()
        except (urllib.error.URLError, OSError):
            return 0  # fzf exited
        current = "\n".join(render_rows())
        if current == last:
            continue
        last = current
        body = "reload(%s %s --list)" % (shlex.quote(PYTHON), shlex.quote(SELF))
        try:
            urllib.request.urlopen(
                urllib.request.Request(base, data=body.encode(), method="POST"),
                timeout=5,
            ).read()
        except (urllib.error.URLError, OSError):
            return 0
    return 0


# --- kitten ---------------------------------------------------------------


def _pick() -> Optional[str]:
    """Run the panel. Returns the chosen pane id, or None."""
    env = dict(os.environ)
    # fzf loads and reloads the list itself, so there is one code path for the
    # first draw and every refresh.
    env["FZF_DEFAULT_COMMAND"] = "%s %s --list" % (shlex.quote(PYTHON), shlex.quote(SELF))

    argv = [
        FZF,
        "--ansi",
        "--no-sort",
        "--layout=reverse",
        "--info=inline",
        "--delimiter=\t",
        "--prompt=herdr pane: ",
        "--header=enter: open here   x: kill pane   esc: cancel",
        "--listen",
        # $FZF_PORT is exported to children of fzf; the loop detaches at once.
        "--bind=start:execute-silent(%s %s --poll $FZF_PORT &)"
        % (shlex.quote(PYTHON), shlex.quote(SELF)),
        "--bind=x:execute-silent(%s %s --kill {1})+reload(%s %s --list)"
        % (shlex.quote(PYTHON), shlex.quote(SELF), shlex.quote(PYTHON), shlex.quote(SELF)),
        "--bind=ctrl-x:execute-silent(%s %s --kill {1})+reload(%s %s --list)"
        % (shlex.quote(PYTHON), shlex.quote(SELF), shlex.quote(PYTHON), shlex.quote(SELF)),
    ]
    try:
        # stderr stays on the terminal: that is where fzf draws its UI.
        proc = subprocess.Popen(argv, stdout=subprocess.PIPE, env=env, text=True)
        out, _ = proc.communicate()
    except (OSError, ValueError):
        return None
    if proc.returncode != 0 or not out.strip():
        return None
    return out.split("\t", 1)[0].strip() or None


def main(args: List[str]) -> str:
    """kitten entry point: returns the pane id to attach, or a marker."""
    # No early exit for an empty fleet: the panel opens either way and says so
    # in its own list, because a kitten that returns before it draws leaves the
    # user looking at an unchanged screen with no idea why.
    pane_id = _pick()
    return pane_id or "CANCELLED"


def handle_result(
    args: List[str], answer: str, target_window_id: int, boss: Boss
) -> None:
    """Attach in the split the panel was opened from, by running the attach in
    that split's own shell."""
    if not _is_pane_id(answer):
        return
    window = boss.window_id_map.get(target_window_id)
    if window is None:
        return
    # write_to_child, not a `send-text` remote control call: remote control
    # matches over every window, and the kitten overlay that just closed is
    # still a dead weakref in kitty's window map at this point, which makes the
    # match raise. Writing straight to this window's child has no such race,
    # and it bypasses bracketed paste, so the carriage return runs the command.
    window.write_to_child("herdr agent attach %s\r" % answer)


if __name__ == "__main__" and not RUNNING_AS_KITTEN:
    argv = sys.argv[1:]
    if argv and argv[0] == "--list":
        raise SystemExit(mode_list())
    if argv and argv[0] == "--kill" and len(argv) > 1:
        raise SystemExit(mode_kill(argv[1]))
    if argv and argv[0] == "--poll" and len(argv) > 1:
        raise SystemExit(mode_poll(argv[1]))
    raise SystemExit("usage: herdr_panel.py [--list | --kill <pane> | --poll <port>]")
