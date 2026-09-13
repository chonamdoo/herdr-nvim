# herdr-nvim

[![CI](https://github.com/chonamdoo/herdr-nvim/actions/workflows/ci.yml/badge.svg)](https://github.com/chonamdoo/herdr-nvim/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/ChmaraX/herdr-nvim)](LICENSE)

Personal portable configuration fork of [ChmaraX/herdr-nvim](https://github.com/ChmaraX/herdr-nvim).
The upstream plugin identity remains `chmarax.herdr-nvim`.

Neovim, built into your [herdr](https://herdr.dev) workspace: a persistent
nvim sidebar one key away, with quick access to the files your agent works on.

<https://github.com/user-attachments/assets/39cff292-fff9-4373-a1e5-7fa56f590c9a>

## Features

- **Full-height nvim sidebar, one key to toggle.** Your panes move into the
  left half, and nvim takes the right. Toggle it off, and herdr restores the
  original layout. Each tab keeps its own persistent nvim, so buffers, cursor,
  and pending annotations survive the toggle.
- **Fuzzy file picker.** It opens on the files your agent touched recently
  (newest first, with diff stats). Type to fuzzy-search the whole repo. `⏎`
  opens the file in the sidebar at the right line.
- **Code annotations you send to the agent.** Comment lines or a selection
  like a code review. Then send them all to any agent in the workspace (pi,
  claude, codex), with file:line and git context.

## Requirements

macOS or Linux, inside Herdr. The bundled editor needs Neovim ≥ 0.11.3,
Herdr ≥ 0.7.4, Python ≥ 3.11, Git ≥ 2.19, Cargo ≥ 1.85, a C toolchain,
`make`, `bash`, `rg`, `fd` (or `fdfind`), `tree-sitter`, `curl`, and `tar`.
Use a Nerd Font in the terminal for tree/status icons. Native Windows is not supported.

## Portable install

On macOS, install the command-line prerequisites (install Herdr separately):

```sh
brew install neovim ripgrep fd python@3.13 tree-sitter-cli
# Install Rust/Cargo with rustup and Apple's command-line tools if missing.
mkdir -p ~/Developer/Aiproject
git clone https://github.com/chonamdoo/herdr-nvim.git ~/Developer/Aiproject/herdr-nvim
cd ~/Developer/Aiproject/herdr-nvim
bash setup.sh --dry-run
bash setup.sh
```

On Linux, install the same prerequisites through your distribution/rustup.
Check Neovim and Python versions: distribution packages may be too old.
Then clone the same repository and run `bash setup.sh`.

The installer builds **this checkout** with `cargo --locked`, links it to Herdr,
copies `setup/nvim` into `${XDG_CONFIG_HOME:-~/.config}/herdr-editor`, and restores
the checked-in `lazy-lock.json`. It also waits for the profile's syntax parsers
to install. It never downloads an upstream Herdr plugin binary.

`NVIM_APPNAME=herdr-editor` isolates editor config, data, state, and cache from
your normal Neovim. `local.lua` is generated on each PC with that PC's checkout
path; do not commit it. Home/XDG paths, `HERDR_CONFIG_PATH`, and
`HERDR_NVIM_CONFIG` are respected.

Herdr bindings are added without replacing existing settings:

| Keys (default prefix is `Ctrl+b`) | Action |
| --- | --- |
| `Ctrl+b`, then `Ctrl+e` | Open/close the sidebar |
| `Ctrl+b`, then `Ctrl+o` | Agent-touched/repo file picker |

Existing `prefix+e` scrollback and `prefix+o` bindings are left alone.
Herdr normally reloads its configuration; if bindings do not appear, use
Herdr's reload-config action. Do not restart agent panes.

### Safety and updates

```sh
bash setup.sh --config-only             # No build, link, or network
bash setup.sh --dry-run                 # Preflight, no writes
bash setup.sh --toggle-key prefix+ctrl+e --picker-key prefix+ctrl+o
git pull --ff-only
bash setup.sh                          # Repeat after an update or checkout move
```

Changed destination files get timestamped `.bak.*` backups. A modified managed
editor file is refused unless you explicitly pass `--replace-profile`, which
backs it up before replacing it. Extra user files are preserved. Edit
`setup/nvim` in the repository and commit your changes to share them across PCs,
rather than editing the installed copy. Existing user-owned conflicting action
bindings or `sidebar.nvim_env` require explicit reconciliation; setup does not
silently erase them. Configuration roots and parent directories are resolved
through symlinks (including macOS `/var`); symlinked managed files and directories
within the editor profile are refused.

Each file replacement is atomic, but the entire installation is not a transaction.
A build, network, or plugin-registration failure stops the installer; completed
steps remain in place for diagnosis and a repeat run. Keep the checkout: Herdr
links it and the Neovim profile loads its local Lua plugin.

Plugin commits and Cargo dependencies are locked. OS tools, fonts, language
servers/formatters installed by Mason, and terminal capabilities are not made
identical by the lockfile. Use the same repository commit and compatible tools
on both PCs; do not use `:Lazy update` on only one PC and expect matching versions.
To deliberately update plugins, update the repository profile's lock through
Lazy, review/test it, commit it, then reinstall on each PC.

### Seeing agent changes

The profile uses [LazyVim](https://github.com/LazyVim/LazyVim), its official
[neo-tree extra](https://www.lazyvim.org/extras/editor/neo-tree), and built-in
[gitsigns](https://github.com/lewis6991/gitsigns.nvim) integration. The tree opens
once on the first UI attachment; reopening the sidebar preserves your layout.

Visible, unmodified files refresh every 750 ms while the sidebar UI is attached,
including atomic file replacements. Unsaved buffers are never overwritten.
Hidden buffers are not polled, and the timer stops when the last UI detaches.
This shows disk saves, not an agent's private in-memory edits; it does not switch
files behind your cursor. Use the touched-file picker to move to another file.

Inside Neovim, `<leader>` is Space:

| Keys | Action |
| --- | --- |
| `<leader>e` | Explorer |
| `<leader>ff` | Find file |
| `<leader>gs` | Changed files |
| `<leader>gd` | Git diff picker |
| `<leader>ghp` | Preview current hunk |
| `<leader>ghd` | Current-file diff |
| `/` | Normal in-buffer search |

Diagnostics remain enabled; format-on-save is disabled to avoid changing code
merely while reviewing it. Existing upstream annotation mappings are below.
Toggle the **Herdr sidebar**, rather than `:qa`, to preserve unsaved buffers.

## The sidebar

`prefix+ctrl+e` toggles it. Each tab gets its own nvim, backed by a headless
daemon that survives the toggle. Two tabs can show two different files in two
sidebars. When you close and reopen a sidebar, it loses nothing. herdr
removes the daemons of closed tabs automatically.

## The file picker

`prefix+ctrl+o` pops a fuzzy file picker. It has two modes:

- **Default view (no query):** the files touched this session, newest first.
  It mines edits from the agent's session log and adds uncommitted git
  changes. For agents that herdr does not track, it scrapes recent pane
  output instead. The cursor starts on the newest file, so `⏎` opens it with
  no typing.
- **Typing:** fuzzy matches across the **whole repo**, ranked best first.
  This includes every file that `git ls-files` reports, and it honors
  `.gitignore`. The match is on the path and filename, not the file contents.

The repo-wide tier is served by [fff-search](https://crates.io/crates/fff-search)
(fff.nvim's core matcher): multi-term queries (`cargo toml`), typo
tolerance, and frecency ranking. If a fff.nvim frecency database exists at
`~/.cache/nvim/fff_nvim`, the picker reuses it read-only (it copies the DB
to a temp dir and opens the copy; your database is never opened, locked, or
written) so files you actually open often rank higher. Set `frecency =
false` to skip the DB reuse. The agent-touched session tier always ranks
first and uses its own matcher regardless.

Each row shows:

- the path, relative to the agent's cwd
- a `new` badge for files created this session
- green/red `+N -M` diff stats for uncommitted edits
- a relative touched-age (`2m`, `3h`)

If you start the picker from a non-agent pane (for example, the sidebar
itself), it reads the agent in the same tab. So it searches the repo that
you see.

The default view shows the latest `max_files` entries (20). A typed query is
uncapped.

## Annotations

Each action has a default keymap and a `:Herdr` subcommand (subcommands
tab-complete):

| Keymap | Command | Action |
| --- | --- | --- |
| `<leader>ac` | `:Herdr comment` | comment the current line / selection (the command also takes a range: `:5,10Herdr comment`) |
| `<leader>al` | `:Herdr list` | list comments (float): hover to jump, `⏎` edit, `d` delete |
| `<leader>as` | `:Herdr send` | paste all comments into the agent's input |
| `<leader>aS` | `:Herdr submit` | send all comments to the agent (auto-submits) |

Keymaps are on by default (prefix `<leader>a`) and never override a map you
already set. To bind your own, set `keymaps = false` and map the command:

```lua
require("herdr-nvim").setup({ keymaps = false })
vim.keymap.set({ "n", "x" }, "<leader>ac", "<CMD>Herdr comment<CR>", { desc = "Comment" })
```

Or call the Lua API directly (`comment_line`, `comment_selection`,
`comment_range(s, e)`, `list_comments`, `send_all{ submit = false|true }`).
See `:help herdr-nvim` for the full reference.

Sending skips the picker when the target is obvious: the lone agent in the
workspace, or the single agent sharing this tab (the sibling pane). The picker
only appears when two or more agents could plausibly be meant.

Comments are ephemeral by design: in-memory only, extmark-tracked (they follow
your edits), cleared after a successful send. The sent prompt includes each
comment's file:line plus the repo and branch, so the agent has context.

For a pending-comment indicator (`● 3`) in your statusline:
`require("herdr-nvim").statusline()`.

## Config

Two small config surfaces, one per half:

**nvim side** — `setup{}` opts:

```lua
require("herdr-nvim").setup({
  prefix = "<leader>a",     -- keymap prefix
  keymaps = true,           -- set false to define your own
  clear_after_send = true,  -- comments are ephemeral by design
})
```

**herdr side** — `~/.config/herdr-nvim/config.toml` (optional; missing or
malformed files fall back to these defaults):

```toml
[sidebar]
nvim_bin = "nvim"     # binary used to spawn the per-tab nvim daemon
nvim_env = []         # env overrides for that nvim, applied to the daemon,
                      # the sidebar window, and open-file clients. For
                      # example, nvim_env = ["NVIM_APPNAME=myapp"] runs the
                      # sidebar under the config in ~/.config/myapp instead
                      # of vanilla nvim (replace myapp with your app name).
position = "right"    # right (default), left, top, or bottom

[picker]
scan_lines = 300    # pane lines scanned by the fallback text-scrape
max_files = 20      # session entries shown before you type a query
                    # (a typed query fuzzy-searches the whole repo, uncapped)
frecency = true     # let fff reuse ~/.cache/nvim/fff_nvim (read-only copy)
```

If your normal nvim config lives under a custom `NVIM_APPNAME` (any name you
launch `nvim` with — e.g. a distro or your own config directory), set
`sidebar.nvim_env = ["NVIM_APPNAME=myapp"]` so the sidebar's daemon and window
run that configuration too. Without it the sidebar is vanilla nvim. The daemon
still injects this plugin's lua over runtimepath after your config loads
(VimEnter fallback), so annotations work under any appname.

## Troubleshooting

```sh
./bin/herdr-nvim doctor                     # live split, toggle and remote-UI checks
./bin/herdr-nvim doctor --with-agent claude # also launch an agent registration check
```

Doctor runs labeled checks in a scratch workspace and always removes them
afterward. The most common failure is `daemon-healthy` FAIL: the nvim daemon
did not start. Make sure that `sidebar.nvim_bin` points at a working nvim ≥
0.11.3 for this bundled profile.

## Tests

```sh
just ci    # Rust formatting/tests, Lua regressions and Python installer tests
# If python3 is older than 3.11 (for example, Apple's system Python):
PYTHON=python3.13 just ci
```
