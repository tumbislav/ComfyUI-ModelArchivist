import adapter from '@sveltejs/adapter-static';
import {vitePreprocess} from '@sveltejs/vite-plugin-svelte';

const config = {
    preprocess: vitePreprocess(),
    kit: {
        paths: {
            base: '/model-archivist'
        },
        adapter: adapter({
            pages: 'build',
            assets: 'build',
            fallback: 'index.html',
            precompress: false,
            strict: true
        }),
        alias: {
			'$lib/*': './src/lib/*',
			'$components/*': './src/lib/components/*',
			'$styles/*': './src/lib/styles/*',
			'$icons/*': './src/lib/assets/icons/*'
        }
    }
};

export default config;
