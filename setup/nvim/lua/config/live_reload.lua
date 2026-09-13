local M = {}
local timer
local queued = false
local new_files = {}
local files = {}

local function regular(buf)
  if not vim.api.nvim_buf_is_loaded(buf) or vim.bo[buf].buftype ~= "" then
    return false
  end
  local name = vim.api.nvim_buf_get_name(buf)
  if name == "" then
    return false
  end
  -- Resolve the path each time, rather than watching an inode: atomic saves
  -- replace the file, and temporarily missing paths can reappear next tick.
  local stat = vim.uv.fs_stat(name)
  return stat and stat.type == "file" and vim.fn.filereadable(name) == 1 and stat
end

-- Explicit entry point for headless checks; the automatic caller requires a UI.
-- Only windows in the current tab are visible to that UI. No repository scans.
function M.refresh()
  local checked = {}
  for _, win in ipairs(vim.api.nvim_tabpage_list_wins(0)) do
    local buf = vim.api.nvim_win_get_buf(win)
    local stat = not checked[buf] and not vim.bo[buf].modified and regular(buf)
    if stat then
      checked[buf] = true
      local previous = files[buf]
      local replaced = previous and (previous.ino ~= stat.ino or previous.dev ~= stat.dev)
      if new_files[buf] or replaced then
        -- :checktime can miss an atomic replacement retaining the timestamp,
        -- or prompt for a BufNewFile created externally (W13).
        -- Plain :edit still refuses to abandon unsaved changes; never use !.
        vim.api.nvim_buf_call(buf, function()
          vim.cmd.edit({ mods = { silent = true, keepalt = true, keepjumps = true } })
        end)
      else
        vim.cmd.checktime({ args = { tostring(buf) }, mods = { silent = true } })
      end
      files[buf] = files[buf] or stat
    end
  end
end

function M.stop()
  if timer then
    timer:stop()
    timer:close()
    timer = nil
  end
end

function M.is_running()
  return timer ~= nil and timer:is_active()
end

local function sync_ui()
  if #vim.api.nvim_list_uis() == 0 then
    M.stop()
  elseif not timer then
    timer = assert(vim.uv.new_timer())
    timer:start(0, 750, function()
      if queued then
        return
      end
      queued = true
      vim.schedule(function()
        queued = false
        if #vim.api.nvim_list_uis() == 0 then
          M.stop()
        elseif timer then
          M.refresh()
        end
      end)
    end)
  end
end

function M.setup()
  M.stop()
  vim.opt.autoread = true
  for _, win in ipairs(vim.api.nvim_tabpage_list_wins(0)) do
    local buf = vim.api.nvim_win_get_buf(win)
    files[buf] = files[buf] or regular(buf) or nil
  end
  local group = vim.api.nvim_create_augroup("herdr_editor_live_reload", { clear = true })
  vim.api.nvim_create_autocmd({ "UIEnter", "UILeave" }, {
    group = group,
    callback = function()
      vim.schedule(sync_ui)
    end,
  })
  vim.api.nvim_create_autocmd("VimLeavePre", { group = group, callback = M.stop })
  vim.api.nvim_create_autocmd("BufNewFile", {
    group = group,
    callback = function(event)
      new_files[event.buf] = true
      files[event.buf] = nil
    end,
  })
  vim.api.nvim_create_autocmd({ "BufReadPost", "BufWritePost", "BufWipeout" }, {
    group = group,
    callback = function(event)
      new_files[event.buf] = nil
      files[event.buf] = event.event ~= "BufWipeout" and regular(event.buf) or nil
      if vim.api.nvim_buf_is_valid(event.buf) then
        vim.b[event.buf].herdr_external_change = nil
      end
    end,
  })
  vim.api.nvim_create_autocmd("FileChangedShell", {
    group = group,
    callback = function(event)
      -- Clean autoread reloads do not trigger this event. A concurrent local
      -- edit or deletion must stay intact, without modal reload prompts.
      vim.v.fcs_choice = ""
      vim.b[event.buf].herdr_external_change = vim.v.fcs_reason
    end,
  })
  sync_ui()
end

return M
