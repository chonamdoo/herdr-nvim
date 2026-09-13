local M = {}
local opened = false

function M.setup()
  local group = vim.api.nvim_create_augroup("herdr_editor_initial_view", { clear = true })
  local function show()
    vim.schedule(function()
      if opened or #vim.api.nvim_list_uis() == 0 then
        return
      end
      opened = true
      -- Keep a file opened by Herdr's picker in focus; otherwise start in the tree.
      local has_file = vim.bo.buftype == "" and vim.api.nvim_buf_get_name(0) ~= ""
      require("neo-tree.command").execute({
        source = "filesystem",
        action = has_file and "show" or "focus",
        dir = vim.fn.getcwd(),
        position = "left",
      })
    end)
  end
  vim.api.nvim_create_autocmd("UIEnter", { group = group, callback = show })
  if #vim.api.nvim_list_uis() > 0 then
    show()
  end
end

return M
