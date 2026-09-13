local lockfile = vim.fn.stdpath("config") .. "/lazy-lock.json"
local ok, lock = pcall(function()
  return vim.json.decode(table.concat(vim.fn.readfile(lockfile), "\n"))
end)
local revision = ok and type(lock) == "table" and type(lock["lazy.nvim"]) == "table"
  and lock["lazy.nvim"].commit
if type(revision) ~= "string" or #revision ~= 40 or not revision:match("^%x+$") then
  error("herdr-editor: a generated lazy-lock.json with the lazy.nvim commit is required; reinstall from a complete checkout")
end

local lazypath = vim.fn.stdpath("data") .. "/lazy/lazy.nvim"
if not vim.uv.fs_stat(lazypath) then
  vim.fn.mkdir(vim.fn.fnamemodify(lazypath, ":h"), "p")
  local staging = lazypath .. ".bootstrap-" .. vim.fn.getpid()
  if vim.uv.fs_stat(staging) then
    error("herdr-editor: bootstrap staging directory already exists: " .. staging)
  end
  local commands = {
    { "git", "clone", "--filter=blob:none", "--no-checkout", "https://github.com/folke/lazy.nvim.git", staging },
    { "git", "-C", staging, "checkout", "--detach", revision },
  }
  for _, command in ipairs(commands) do
    local output = vim.fn.system(command)
    if vim.v.shell_error ~= 0 then
      vim.fn.delete(staging, "rf")
      error("herdr-editor: locked lazy.nvim bootstrap failed:\n" .. output)
    end
  end
  local renamed, err = vim.uv.fs_rename(staging, lazypath)
  if not renamed then
    vim.fn.delete(staging, "rf")
    error("herdr-editor: could not install lazy.nvim: " .. tostring(err))
  end
end
local installed = vim.fn.system({ "git", "-C", lazypath, "rev-parse", "HEAD" })
if vim.v.shell_error ~= 0 or vim.trim(installed) ~= revision then
  error("herdr-editor: installed lazy.nvim differs from lazy-lock.json; rerun the portable installer to restore the locked revision")
end
vim.opt.rtp:prepend(lazypath)

require("lazy").setup({
  spec = {
    { "LazyVim/LazyVim", import = "lazyvim.plugins" },
    { import = "lazyvim.plugins.extras.editor.neo-tree" },
    { import = "plugins" },
  },
  lockfile = lockfile,
  defaults = { lazy = false, version = false },
  install = { colorscheme = { "catppuccin", "habamax" } },
  checker = { enabled = false },
  change_detection = { notify = false },
  performance = {
    rtp = {
      disabled_plugins = { "gzip", "tarPlugin", "tohtml", "tutor", "zipPlugin" },
    },
  },
})
