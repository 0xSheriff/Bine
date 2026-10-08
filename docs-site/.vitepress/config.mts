import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'BINE',
  description: 'Pre-trade safety check for tokenized stocks on BNB Smart Chain (chainId 56).',
  appearance: true,
  cleanUrls: true,
  themeConfig: {
    siteTitle: 'BINE Docs',
    nav: [
      { text: 'Overview', link: '/' },
      { text: 'Quickstart', link: '/quickstart' },
      { text: '8 Rules', link: '/how-bine-decides' },
      { text: 'API Reference', link: '/api-reference' },
      { text: 'CLI & MCP', link: '/cli-and-mcp' },
      { text: 'Evidence', link: '/evidence' },
      { text: 'DevEx Findings', link: '/devex-findings' },
      { text: 'Limits', link: '/limits' },
    ],
    sidebar: [
      {
        text: 'Getting Started',
        items: [
          { text: '1. Overview', link: '/' },
          { text: '2. Quickstart', link: '/quickstart' },
        ],
      },
      {
        text: 'Decision Engine & Reference',
        items: [
          { text: '3. How BINE Decides', link: '/how-bine-decides' },
          { text: '4. API Reference', link: '/api-reference' },
          { text: '5. CLI and MCP', link: '/cli-and-mcp' },
        ],
      },
      {
        text: 'Verification & Audit',
        items: [
          { text: '6. On-Chain Evidence', link: '/evidence' },
          { text: '7. Developer Experience Findings', link: '/devex-findings' },
          { text: '8. Known Limits', link: '/limits' },
        ],
      },
    ],
    search: {
      provider: 'local',
    },
    footer: {
      message: 'BINE Pre-Trade Guard for Tokenized Stocks on BNB Smart Chain (chainId 56).',
    },
  },
})
