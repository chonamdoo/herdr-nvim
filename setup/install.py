#!/usr/bin/env python3
"""Install the local fork and its isolated editor profile; no third-party Python packages."""

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib

ROOT = Path(__file__).resolve().parent.parent
APPNAME = "herdr-editor"
PLUGIN = "chmarax.herdr-nvim"
STATE = ".herdr-editor-managed.json"
TOGGLE = "prefix+ctrl+e"
PICKER = "prefix+ctrl+o"


class InstallError(Exception):
    pass


def parse_toml(text, label):
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise InstallError(f"Invalid TOML in {label}: {error}") from error


def read_text(path):
    if path.exists() and not path.is_file():
        raise InstallError(f"Expected a file: {path}")
    if not path.exists():
        return ""
    with path.open(encoding="utf-8", newline="") as stream:
        return stream.read()


def markers(name):
    return (f"# BEGIN herdr-editor managed {name}\n", f"# END herdr-editor managed {name}\n")


def remove_block(text, name):
    begin, end = markers(name)
    # A malformed marker must never turn into a second managed block.
    lines = text.splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.rstrip("\r\n") == begin.rstrip("\n")]
    ends = [i for i, line in enumerate(lines) if line.rstrip("\r\n") == end.rstrip("\n")]
    if not starts and not ends:
        return text
    if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
        raise InstallError(f"Malformed managed {name} markers; repair them before installing")
    payload = "".join(lines[starts[0] + 1:ends[0]])
    if name == "keys":
        data = parse_toml(payload, "managed keys")
        entries = data.get("keys", {}).get("command", [])
        if set(data) != {"keys"} or set(data["keys"]) != {"command"} or not isinstance(entries, list):
            raise InstallError("Managed keys block contains unrelated settings; move them outside the block")
        if any(not isinstance(item, dict) or item.get("command") not in {f"{PLUGIN}.toggle", f"{PLUGIN}.pick-file"}
               or set(item) - {"key", "type", "command", "description"} for item in entries):
            raise InstallError("Managed keys block contains user bindings; move them outside the block")
    else:
        data = parse_toml(payload, "managed sidebar")
        if data not in ({"nvim_env": data.get("nvim_env")}, {"sidebar": data.get("sidebar")}):
            raise InstallError("Managed sidebar block contains unrelated settings")
        fields = data.get("sidebar", data)
        if not isinstance(fields, dict) or set(fields) != {"nvim_env"}:
            raise InstallError("Managed sidebar block contains unrelated settings")
    return "".join(lines[:starts[0]] + lines[ends[0] + 1:])


def block(name, payload):
    begin, end = markers(name)
    return begin + payload + end


def append_block(text, addition):
    separator = "" if not text or text.endswith("\n\n") else "\n" if text.endswith("\n") else "\n\n"
    return text + separator + addition


def key_id(value):
    if not isinstance(value, str):
        raise InstallError("Key bindings must be strings or lists of strings")
    parts = value.strip().split("+")
    aliases = {"control": "ctrl", "c": "ctrl", "option": "alt", "meta": "alt", "m": "alt", "s": "shift"}
    modifiers = [aliases.get(part.lower(), part.lower()) for part in parts[:-1]]
    if not parts[-1] or any(part not in {"prefix", "ctrl", "alt", "shift", "super"} for part in modifiers):
        # Unknown existing formats are still compared literally, never rewritten.
        return value.strip()
    key = parts[-1]
    if len(key) == 1 and key.isupper():
        modifiers.append("shift")
        key = key.lower()
    return "+".join(sorted(set(modifiers)) + [key])


def binding_keys(value):
    # Herdr has named scalar bindings, list-valued bindings, and [[keys.command]].
    if isinstance(value, dict):
        for name, child in value.items():
            if name not in {"command", "description", "type"} or isinstance(child, (dict, list)):
                yield from binding_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from binding_keys(child)
    elif isinstance(value, str):
        yield key_id(value)


def run(command, *, capture=False, env=None, cwd=ROOT):
    print("+ " + shlex.join(str(arg) for arg in command), flush=True)
    try:
        result = subprocess.run(command, check=True, text=True, capture_output=capture, env=env, cwd=cwd)
    except (OSError, subprocess.CalledProcessError) as error:
        detail = (error.stderr or error.stdout or "").strip() if isinstance(error, subprocess.CalledProcessError) else str(error)
        raise InstallError(f"Command failed: {shlex.join(str(arg) for arg in command)}\n{detail}") from error
    return result.stdout if capture else None


def executable(name):
    return shutil.which(name)


def require_version(name, minimum, arguments=("--version",)):
    program = executable(name)
    if not program:
        raise InstallError(f"Required executable not found: {name}")
    output = run([program, *arguments], capture=True)
    match = re.search(r"\b(?:v)?(\d+)\.(\d+)\.(\d+)", output)
    if not match or tuple(map(int, match.groups())) < minimum:
        raise InstallError(f"{name} >= {'.'.join(map(str, minimum))} required; got {output.strip()}")
    return program


def configure_keys(original, toggle, picker, herdr):
    original_data = parse_toml(original, "Herdr config")
    text = remove_block(original, "keys")
    data = parse_toml(text, "Herdr config without managed keys")
    if text != original:
        expected_remaining = copy.deepcopy(original_data)
        entries = expected_remaining.get("keys", {}).get("command", [])
        if not isinstance(entries, list):
            raise InstallError("Unsupported managed keys table")
        expected_remaining.setdefault("keys", {})["command"] = [
            item for item in entries
            if item.get("command") not in {f"{PLUGIN}.toggle", f"{PLUGIN}.pick-file"}
        ]
        comparable = copy.deepcopy(data)
        for config in (expected_remaining, comparable):
            if config.get("keys", {}).get("command") == []:
                del config["keys"]["command"]
            if config.get("keys") == {}:
                del config["keys"]
        if expected_remaining != comparable:
            raise InstallError("Managed keys markers cross user-owned TOML; move user settings outside the managed tables")
    requested = [key_id(toggle), key_id(picker)]
    if requested[0] == requested[1]:
        raise InstallError("Toggle and picker keys must differ")
    for key in (toggle, picker):
        if not re.fullmatch(r"prefix\+(?:(?:ctrl|alt|shift|super)\+)*[A-Za-z0-9]", key):
            raise InstallError(f"Unsupported key {key!r}: use prefix+[ctrl+|alt+|shift+|super+]letter-or-digit")
    if herdr:
        default_text = run([herdr, "--default-config"], capture=True)
        defaults = parse_toml(default_text, "herdr --default-config")
        reserved = set(binding_keys(defaults.get("keys", {})))
        # Herdr 0.9 prints effective defaults as commented assignments. Parsing
        # that template as TOML alone produces an empty keys table.
        in_keys = False
        for line in default_text.splitlines():
            if line.startswith("["):
                in_keys = line.strip() == "[keys]"
            assignment = re.fullmatch(r'# ([A-Za-z_]\w*\s*=\s*(?:"[^"]*"|\[[^\]]*\])\s*(?:#.*)?)', line)
            if in_keys and assignment:
                reserved.update(binding_keys(parse_toml(assignment[1], "commented Herdr key default")))
    else:
        # Without a running/installed Herdr, a partial hand-copied default table
        # would give false confidence. Only the two reviewed project chords are
        # allowed. Other chords require querying the installed Herdr defaults.
        print("Herdr unavailable: conservative offline key policy permits only prefix+ctrl+e and prefix+ctrl+o.")
        if any(key not in {key_id(TOGGLE), key_id(PICKER)} for key in requested):
            raise InstallError("Custom keys require Herdr so --default-config can be checked")
        reserved = {key_id("prefix+e"), key_id("prefix+o")}
    keys = data.get("keys", {})
    if not isinstance(keys, dict):
        raise InstallError("Unsupported Herdr keys table")
    commands = keys.get("command", [])
    if not isinstance(commands, list) or any(not isinstance(item, dict) for item in commands):
        raise InstallError("Unsupported keys.command shape; expected [[keys.command]] entries")
    for item in commands:
        if item.get("command") in {f"{PLUGIN}.toggle", f"{PLUGIN}.pick-file"}:
            raise InstallError("Sidebar action already has a user-owned binding; remove it explicitly before setup manages it")
    reserved.update(binding_keys(keys))
    for raw, normalized in zip((toggle, picker), requested):
        if normalized in reserved:
            raise InstallError(f"Key collision: {raw} is reserved by Herdr defaults or existing configuration")
    additions = []
    for key, action, description in ((toggle, "toggle", "nvim sidebar"), (picker, "pick-file", "open file from agent output")):
        additions.append({"key": key, "type": "plugin_action", "command": f"{PLUGIN}.{action}", "description": description})
    payload = "\n".join("[[keys.command]]\n" + "".join(f"{name} = {json.dumps(value)}\n" for name, value in item.items()) for item in additions)
    result = append_block(text, block("keys", payload))
    expected = copy.deepcopy(data)
    expected.setdefault("keys", {}).setdefault("command", []).extend(additions)
    if parse_toml(result, "proposed Herdr config") != expected:
        raise InstallError("Unsupported Herdr TOML layout; no files changed")
    return result


def configure_sidebar(original, config_home):
    original_data = parse_toml(original, "herdr-nvim config")
    text = remove_block(original, "sidebar")
    data = parse_toml(text, "herdr-nvim config without managed sidebar")
    if text != original:
        expected_remaining = copy.deepcopy(original_data)
        expected_remaining.get("sidebar", {}).pop("nvim_env", None)
        if expected_remaining != data:
            raise InstallError("Managed sidebar markers cross user-owned TOML; no files changed")
    sidebar = data.get("sidebar", {})
    if not isinstance(sidebar, dict):
        raise InstallError("Unsupported sidebar table; no files changed")
    nvim_bin = sidebar.get("nvim_bin", "nvim")
    if not isinstance(nvim_bin, str) or not nvim_bin.strip() or "\x00" in nvim_bin:
        raise InstallError("sidebar.nvim_bin must be a nonempty executable path")
    environment = [f"NVIM_APPNAME={APPNAME}", f"XDG_CONFIG_HOME={config_home}"]
    if "nvim_env" in sidebar:
        if sidebar["nvim_env"] == environment:
            return text, nvim_bin
        raise InstallError("User-owned sidebar.nvim_env conflicts with the isolated profile; move/remove it explicitly (other sidebar settings are preserved)")
    payload = f"nvim_env = {json.dumps(environment, ensure_ascii=False)}\n"
    header = re.search(r"(?m)^[ \t]*\[[ \t]*(?:sidebar|\"sidebar\"|'sidebar')[ \t]*\][ \t]*(?:#[^\r\n]*)?(?:\r?\n|$)", text)
    if header:
        prefix = text[:header.end()]
        if not prefix.endswith("\n"):
            prefix += "\n"
        result = prefix + block("sidebar", payload) + text[header.end():]
    elif "sidebar" not in data:
        result = append_block(text, "[sidebar]\n" + block("sidebar", payload))
    else:
        raise InstallError("Unsupported sidebar TOML layout; use an explicit [sidebar] table before setup")
    expected = copy.deepcopy(data)
    expected.setdefault("sidebar", {})["nvim_env"] = environment
    if parse_toml(result, "proposed herdr-nvim config") != expected:
        raise InstallError("Unsupported sidebar TOML layout; no files changed")
    return result, nvim_bin


def digest(content):
    return hashlib.sha256(content).hexdigest()


def check_destination(path):
    for parent in (path, *path.parents):
        if parent.is_symlink():
            raise InstallError(f"Refusing managed destination through symlink: {parent}")
    if path.exists() and not path.is_file():
        raise InstallError(f"Expected a regular file: {path}")


def profile_plan(profile, replace):
    source = ROOT / "setup" / "nvim"
    if not (source / "init.lua").is_file():
        raise InstallError(f"Missing versioned profile: {source / 'init.lua'}")
    desired = {}
    for file in sorted(source.rglob("*")):
        if file.is_symlink():
            raise InstallError(f"Profile sources must not contain symlinks: {file}")
        if file.is_file():
            desired[file.relative_to(source).as_posix()] = file.read_bytes()
    # A Lua long string avoids JSON's incompatible Unicode escape syntax.
    delimiter = "="
    while f"]{delimiter}]" in str(ROOT):
        delimiter += "="
    desired["local.lua"] = f"-- Generated by setup.sh; rerun setup after moving the checkout.\nreturn [{delimiter}[{ROOT}]{delimiter}]\n".encode()
    state_path = profile / STATE
    check_destination(state_path)
    state_text = read_text(state_path)
    previous = {}
    if state_text:
        try:
            state = json.loads(state_text)
            if state.get("version") != 1 or not isinstance(state.get("files"), dict):
                raise ValueError("unsupported manifest")
            previous = state["files"]
            for name, checksum in previous.items():
                relative = Path(name)
                if relative.is_absolute() or ".." in relative.parts or name == STATE or not isinstance(checksum, str):
                    raise ValueError("invalid managed file entry")
        except (ValueError, AttributeError) as error:
            raise InstallError(f"Invalid managed profile manifest {state_path}: {error}") from error
    changes = []
    for name in sorted(set(previous) | set(desired)):
        target = profile / name
        check_destination(target)
        current = target.read_bytes() if target.exists() else None
        wanted = desired.get(name)
        if current == wanted:
            continue
        modified = current is not None and digest(current) != previous.get(name)
        deleted = current is None and name in previous
        if (modified or deleted) and not replace:
            raise InstallError(f"User-modified profile file: {target}; use --replace-profile to replace it with backups")
        changes.append((target, wanted))
    state = {"version": 1, "checkout": str(ROOT), "files": {name: digest(content) for name, content in sorted(desired.items())}}
    changes.append((state_path, (json.dumps(state, indent=2, ensure_ascii=False) + "\n").encode()))
    return changes


def apply_changes(changes, dry_run):
    for path, content in changes:
        current = path.read_bytes() if path.exists() else None
        if current == content:
            continue
        print(f"{'Would ' if dry_run else ''}{'remove' if content is None else 'write'} {path}")
        if dry_run:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if current is not None:
            backup = path.with_name(f"{path.name}.bak.{time.time_ns()}")
            shutil.copy2(path, backup)
            print(f"Backup: {backup}")
        if content is None:
            path.unlink()
        else:
            descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(content)
                if path.exists():
                    os.chmod(temporary, path.stat().st_mode & 0o777)
                os.replace(temporary, path)
            finally:
                Path(temporary).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, epilog="Without Herdr, config-only permits only the reviewed prefix+ctrl+e/o chords. Existing/default keys are conservatively reserved, even if overridden. No files change in dry-run.")
    parser.add_argument("--dry-run", action="store_true", help="preflight and print changes without writing/building/linking/downloading")
    parser.add_argument("--config-only", action="store_true", help="configure only; no builds, plugin registration, or network (Herdr/Neovim not required)")
    parser.add_argument("--replace-profile", action="store_true", help="replace modified managed profile files, keeping backups; preserve extra user files")
    parser.add_argument("--toggle-key", default=TOGGLE)
    parser.add_argument("--picker-key", default=PICKER)
    args = parser.parse_args()
    if sys.platform not in {"darwin", "linux"}:
        raise InstallError("Only macOS and Linux are supported")
    if not os.environ.get("HOME"):
        raise InstallError("HOME must be set")
    # Herdr plugin processes and minimal shells commonly omit Homebrew.
    os.environ["PATH"] = os.pathsep.join(filter(None, [os.environ.get("PATH", ""), "/opt/homebrew/bin", "/usr/local/bin", str(Path.home() / ".cargo/bin")]))
    home = Path(os.environ["HOME"]).expanduser().resolve()
    config_home = Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config").expanduser().resolve()
    herdr_config = Path(os.environ.get("HERDR_CONFIG_PATH") or config_home / "herdr/config.toml").expanduser().absolute()
    plugin_config = Path(os.environ.get("HERDR_NVIM_CONFIG") or config_home / "herdr-nvim/config.toml").expanduser().absolute()
    herdr_config = herdr_config.parent.resolve() / herdr_config.name
    plugin_config = plugin_config.parent.resolve() / plugin_config.name
    profile = config_home / APPNAME
    if herdr_config == plugin_config or profile == ROOT or ROOT in profile.parents or profile in ROOT.parents:
        raise InstallError("Configuration destinations must be distinct from each other and the source checkout")
    for path in (herdr_config, plugin_config):
        check_destination(path)
        if path == profile or profile in path.parents or path == ROOT or ROOT in path.parents:
            raise InstallError(f"Config destination overlaps profile/source: {path}")
    herdr = executable("herdr")
    # All TOML and ownership checks happen before the first write or build.
    herdr_text = configure_keys(read_text(herdr_config), args.toggle_key, args.picker_key, herdr)
    plugin_text, nvim_bin = configure_sidebar(read_text(plugin_config), config_home)
    changes = profile_plan(profile, args.replace_profile)
    changes += [(herdr_config, herdr_text.encode()), (plugin_config, plugin_text.encode())]
    if not args.config_only:
        manifest = parse_toml(read_text(ROOT / "herdr-plugin.toml"), "plugin manifest")
        minimum = tuple(map(int, manifest["min_herdr_version"].split(".")))
        herdr = require_version("herdr", minimum)
        require_version(nvim_bin, (0, 11, 3))
        require_version("git", (2, 19, 0))
        require_version("cargo", (1, 85, 0))
        for program in ("bash", "cc", "make", "rg", "tree-sitter", "curl", "tar"):
            if not executable(program):
                raise InstallError(f"Required executable not found: {program}")
        if not executable("fd") and not executable("fdfind"):
            raise InstallError("Required executable not found: fd (or Debian's fdfind)")
        lock = ROOT / "setup/nvim/lazy-lock.json"
        if not lock.is_file():
            raise InstallError(f"Missing checked-in Lazy lockfile: {lock}")
        lock_data = json.loads(lock.read_text(encoding="utf-8"))
        if not isinstance(lock_data, dict) or "lazy.nvim" not in lock_data or any(
            not isinstance(item, dict) or not re.fullmatch(r"[0-9a-fA-F]{40}", item.get("commit", ""))
            for item in lock_data.values()
        ):
            raise InstallError(f"Invalid checked-in Lazy lockfile: {lock}")
        lazy_revision = lock_data["lazy.nvim"]["commit"]
        data_home = Path(os.environ.get("XDG_DATA_HOME") or home / ".local/share").expanduser().resolve()
        lazy_path = data_home / APPNAME / "lazy/lazy.nvim"
        lazy_needs_checkout = lazy_path.exists() and run(
            ["git", "-C", str(lazy_path), "rev-parse", "HEAD"], capture=True
        ).strip() != lazy_revision
        if lazy_needs_checkout and run(
            ["git", "-C", str(lazy_path), "status", "--porcelain"], capture=True
        ).strip():
            raise InstallError(f"Lazy manager has local edits: {lazy_path}; save them before restoring its locked revision")
    if args.dry_run:
        apply_changes(changes, True)
        if not args.config_only:
            print(f"Would build local fork with cargo --locked, link {ROOT}, and restore checked-in Lazy lock headlessly")
            if lazy_needs_checkout:
                print(f"Would restore lazy.nvim at {lazy_path} to {lazy_revision} without forcing local changes")
        return
    if not args.config_only:
        run(["bash", str(ROOT / "herdr/install.sh")])
    apply_changes(changes, False)
    if not args.config_only:
        run([herdr, "plugin", "link", str(ROOT)])
        environment = dict(os.environ, NVIM_APPNAME=APPNAME, XDG_CONFIG_HOME=str(config_home))
        if lazy_needs_checkout:
            run(["git", "-C", str(lazy_path), "fetch", "origin", lazy_revision])
            run(["git", "-C", str(lazy_path), "checkout", "--detach", lazy_revision])
        # :Lazy! restore alone can exit zero despite a failed plugin build.
        # Inspect the pinned manager's task results and explicitly fail Neovim.
        restore = """
local ok, err = xpcall(function()
  if vim.v.errmsg ~= '' then error(vim.v.errmsg) end
  require('lazy').restore({ wait = true, show = false })
  if vim.v.errmsg ~= '' then error(vim.v.errmsg) end
  local plugins = require('lazy.core.config').plugins
  assert(plugins.LazyVim, 'LazyVim profile did not load')
  for name, plugin in pairs(plugins) do
    assert(plugin._.installed, name .. ' was not installed')
    for _, task in ipairs(plugin._.tasks or {}) do
      assert(not task:has_errors(), name .. ': ' .. tostring(task.output))
    end
  end
  local parsers = LazyVim.opts('nvim-treesitter').ensure_installed or {}
  assert(require('nvim-treesitter').install(parsers):wait(300000), 'Tree-sitter parser installation failed')
  local installed = require('nvim-treesitter').get_installed()
  for _, parser in ipairs(parsers) do
    assert(vim.tbl_contains(installed, parser), 'Missing tree-sitter parser: ' .. parser)
  end
end, debug.traceback)
if not ok then
  vim.api.nvim_err_writeln(tostring(err))
  vim.cmd('cquit 1')
else
  vim.cmd('qa')
end
"""
        run([nvim_bin, "--headless", "-c", "lua " + restore], env=environment)
        if (profile / "lazy-lock.json").read_bytes() != lock.read_bytes():
            raise InstallError("Lazy changed the installed lockfile; review its output and rerun with --replace-profile to restore the checked-in lock")
    print(f"Configured {profile}; toggle {args.toggle_key}, picker {args.picker_key}.")
    if args.config_only:
        print("Configuration only: build, Herdr registration, and Lazy restore were not performed.")


if __name__ == "__main__":
    try:
        main()
    except (InstallError, OSError, ValueError) as error:
        print(f"setup: {error}", file=sys.stderr)
        sys.exit(1)
