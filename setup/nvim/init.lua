local profile = vim.fn.stdpath("config")
local ok, root = pcall(dofile, profile .. "/local.lua")
if not ok or type(root) ~= "string" or root:sub(1, 1) ~= "/" then
  error("herdr-editor: local.lua must return the absolute checkout path; rerun the portable installer")
end
root = vim.uv.fs_realpath(root)
if not root or vim.fn.filereadable(root .. "/lua/herdr-nvim/init.lua") ~= 1
  or vim.fn.filereadable(root .. "/herdr-plugin.toml") ~= 1 then
  error("herdr-editor: local.lua points to a missing herdr-nvim checkout; rerun the portable installer")
end
vim.g.herdr_nvim_root = root
vim.g.mapleader = " "
vim.g.maplocalleader = "\\"

require("config.lazy")
require("config.initial_view").setup()
