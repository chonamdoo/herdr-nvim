return {
  {
    "LazyVim/LazyVim",
    opts = {
      colorscheme = "catppuccin",
      news = { lazyvim = false, neovim = false },
    },
  },
  { "folke/snacks.nvim", opts = { dashboard = { enabled = false } } },
  {
    dir = vim.g.herdr_nvim_root,
    name = "herdr-nvim",
    lazy = false,
    opts = {},
  },
  {
    "folke/which-key.nvim",
    opts = {
      spec = {
        { "<leader>a", group = "agent annotations", mode = { "n", "x" } },
      },
    },
  },
  {
    "nvim-lualine/lualine.nvim",
    opts = function(_, opts)
      table.insert(opts.sections.lualine_x, {
        function()
          return require("herdr-nvim").statusline()
        end,
      })
      table.insert(opts.sections.lualine_c, {
        function()
          local change = vim.b.herdr_external_change
          return change and ("Disk: " .. change) or ""
        end,
        color = { fg = "#f9e2af" },
      })
    end,
  },
}
