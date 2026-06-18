import { defineConfig } from 'vite';

// Pure static, multi-page build:
//  - index.html  → the citation map (reads data/papers.json at build time)
//  - public/     → copied verbatim into dist/, so /papers/<slug>.html resolves
export default defineConfig({
  root: '.',
  publicDir: 'public',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});
