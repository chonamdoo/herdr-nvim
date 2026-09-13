-- Replace broad focus-driven checks with guarded visible-buffer refresh.
vim.api.nvim_del_augroup_by_name("lazyvim_checktime")
-- Remote UI reattachment must not equalize the user's Neovim splits.
vim.api.nvim_del_augroup_by_name("lazyvim_resize_splits")
require("config.live_reload").setup()
