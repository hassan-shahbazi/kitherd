# kitherd

Native AI Agent Orchestration in Kitty Terminal through Herdr. `kitherd` aims to bridge AI agent orchestration and terminal ergonomics, for those who are not comfortable with using a Terminal Multiplexer and are comfortable with their Kitty Terminal and its defined keybindings and configurations.

I have been using this system for months, and it has been a game-changer for my day-to-day productivity. As the result, I decided to make it available publicly for anyone else who has the same needs as I do. I hope you find it useful!

> [!NOTE]
> This is not a commercial project, and it is built based on my own needs and preferences. You are free to fork and modify it based on yours, and if you feel it can be helpful for others, feel free to open a PR.
> However, please avoid re-inventing the wheel; this is not supposed to be a full replacement for Herdr, or an standalone AI agent orchestration system, at least not yet.


## How It Works

```
                        ┌────────────────────────────────────────────────┐
                        │              Kitty Terminal (GUI)              │
                        │                                                │
                        │  ┌───────────────────┐  ┌───────────────────┐  │
                        │  │ Coordinator Agent │  │  Worker Agent 1   │  │
                        │  │  (Master prompt)  │  │  (Native vsplit)  │  │
                        │  └─────────┬─────────┘  └─────────▲─────────┘  │
                        │            │                      │            │
                        │            │ kitty @ launch       │ attach     │
                        └────────────┼──────────────────────┼────────────┘
                                     │                      │
                                     ▼                      │
                        ┌───────────────────────────────────┴────────────┐
                        │      Headless Herdr Daemon (Background)        │
                        │                                                │
                        │  • Workspace: w1 (~/projects/my-app)           │
                        │    ├─ Pane w1:p1: Worker 1 (Claude Code)       │
                        │    ├─ Pane w1:p2: Worker 2 (Codex)             │
                        │    └─ Pane w1:p3: Worker 3 (Antigravity CLI)   │
                        └────────────────────────────────────────────────┘
                                                ▲
                                                │ alt+a (fzf panel)
                                                │
                                     [ Kitty Kitten UI ]
```

### Features

- **Headless Server:** Herdr runs as a headless background daemon on the default session (via systemd, launchd, or background process). It holds all pane state, shell sessions, and agent lifecycles independently of any terminal UI.
- **Native Window Management:** Rather than viewing agents inside an in-terminal multiplexer TUI, the coordinator agent launches native Kitty splits (`kitty @ launch ... herdr agent attach <worker>`). Closing a Kitty split merely detaches the view; the worker agent continues running undisturbed. The agent can be re-attached to any split at any time, or killed if no longer needed.
- **Fast Interactive Switcher:** Pressing `alt+a` opens an overlay with real-time agent status (working, blocked, idle, done), allowing you to re-attach into any split or kill runaway workers with a single keystroke.


## Requirements

### Herder: Server, Integrations, and Skills

All the orchestrations are handled by [Herdr](https://herdr.dev). Make sure you have the following installed and running:

- **[Herder Skills](https://herdr.dev/docs/agent-skill/)**: Allows `kitherd` skills to communicate with the Herdr server.
- **[Herdr Agents Integrations](https://herdr.dev/docs/integrations/)**: These integrations are necessary for efficient harness communications.

### Enable Kitty Remote Control

You need to enable [remote control](https://sw.kovidgoyal.net/kitty/remote-control/) for Kitty to allow the coordinator agent to spawn and attach worker agents in native splits:

```conf
allow_remote_control yes
listen_on unix:/tmp/kitty-remote-control
```

### Agent Switcher Panel (Optional)

Agents are orchestrated through Herder in the background; they do not necessary have to be attached to a terminal split to work. This feature lets you spawn several agents in parallel, or re-use any agent that is sit idle after the work is done, if you do not care about the workers' status.

- To send an agent in the backround, you can simply detach the split by closing it.
- To re-attach to an agent, you can use the switcher panel to select the agent and attach it to a new split.

> [!NOTE]
> The feature is optional, and you can still use the `kitherd` skill without it. The `herdr_panel.py` script is only required if you want to use the interactive switcher panel.

1. Make sure you have `python3` and [fzf](https://github.com/junegunn/fzf) on your system.
2. Define a keybinding in your `kitty.conf` to launch the agent switcher panel (e.g. `alt+a`):
    ```conf
    # Keybinding for the Herdr agent switcher panel
    map alt+a kitten herdr_panel.py
    ```
3. Reload your Kitty configuration or restart Kitty.
4. Press `alt+a` to open the interactive switcher panel and manage your agents. You can then select an agent to attach to a new split, or kill an agent if it is no longer needed:
    ```
    herdr pane: 
    w1:p1   ● working   claude             ~/src/kitherd
    w1:p2   ● blocked   codex              ~/src/kitherd
    w1:p3   ● idle      antigravity        ~/src/kitherd
    > enter: open here   x: kill pane   esc: cancel
    ```

## Installation & Usage

### Nix / NixOS (Home Manager)

Add `kitherd` to your `flake.nix` inputs:

```nix
inputs = {
  nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
  kitherd = {
    url = "github:hassan-shahbazi/kitherd";
    inputs.nixpkgs.follows = "nixpkgs";
  };
};
```

Import the Home Manager module into your configuration and enable it:

```nix
{ inputs, ... }:
{
  imports = [
    inputs.kitherd.homeManagerModules.default
  ];

  programs.kitherd.enable = true;
}
```

This automatically:
- Installs `herdr_panel.py` into `~/.config/kitty/herdr_panel.py`.
- Installs the `kitherd` skill into `~/.agents/skills/kitherd`.
- Ensures runtime dependencies (`python3`, `fzf`) are available.

### Manual / Makefile

Clone the repository and install the skill:

```bash
$ git clone https://github.com/hassan-shahbazi/kitherd.git
$ cd kitherd

# Install the skill (make sure you have `skills` in your PATH)
$ make install

# if you don't have `skills` in your PATH
$ make install SKILLS_CLI="bunx skills"
$ make install SKILLS_CLI="npx skills"
```
