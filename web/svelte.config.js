import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

export default {
  // TypeScript inside <script lang="ts"> blocks is stripped by esbuild via Vite.
  preprocess: vitePreprocess(),
};
