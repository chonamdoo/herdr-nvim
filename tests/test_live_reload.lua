-- Runs with the existing tests/run.lua harness.
local root = vim.fn.fnamemodify(debug.getinfo(1, "S").source:sub(2), ":p:h:h")
T.test("live reload preserves user edits across agent atomic saves", function()
  local runtimepath = vim.o.runtimepath
  local autoread = vim.go.autoread
  local previous_module = package.loaded["config.live_reload"]
  local reload
  vim.opt.rtp:prepend(root .. "/setup/nvim")
  local temp = vim.fn.tempname()
  vim.fn.mkdir(temp, "p")
  local file = temp .. "/agent.lua"
  local ok, err = xpcall(function()
    reload = require("config.live_reload")
    vim.fn.writefile({ "original" }, file)
    vim.cmd.edit(vim.fn.fnameescape(file))
    vim.opt.autoread = true
    reload.setup()
    -- Atomic saves are common in agent tools; do not watch only the old inode.
    local replacement = temp .. "/replacement"
    vim.fn.writefile({ "agent changed this line", "another line" }, replacement)
    assert(vim.uv.fs_rename(replacement, file))
    reload.refresh()
    assert(
      vim.api.nvim_buf_get_lines(0, 0, -1, false)[1] == "agent changed this line",
      "visible clean buffer must show an external atomic save"
    )
    vim.api.nvim_buf_set_lines(0, 0, -1, false, { "my unsaved work" })
    vim.fn.writefile({ "agent saved again", "a", "b" }, file)
    reload.refresh()
    assert(
      vim.api.nvim_buf_get_lines(0, 0, -1, false)[1] == "my unsaved work",
      "external edits must not replace unsaved user work"
    )
    assert(vim.bo.modified, "unsaved buffer must stay modified")
    assert(vim.fn.readfile(file)[1] == "agent saved again", "refresh must never write back over agent edits")
  end, debug.traceback)
  if reload then
    reload.stop()
    vim.api.nvim_del_augroup_by_name("herdr_editor_live_reload")
  end
  vim.o.runtimepath = runtimepath
  vim.go.autoread = autoread
  package.loaded["config.live_reload"] = previous_module
  vim.fn.delete(temp, "rf")
  vim.cmd("bwipeout!")
  assert(ok, err)
end)
