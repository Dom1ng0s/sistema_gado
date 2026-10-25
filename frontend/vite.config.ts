import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import { VitePWA } from 'vite-plugin-pwa';

const API_TARGET = process.env.VITE_API_TARGET || 'http://127.0.0.1:5000';

export default defineConfig({
  plugins: [
    svelte(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.ico', 'fonts/*.woff2'],
      manifest: {
        name: 'SGG — Sistema de Gestão de Gado',
        short_name: 'SGG',
        description: 'Instrumento de gestão zootécnica, GMD, curral e financeiro para pecuária de corte.',
        theme_color: '#0B6E4F',
        background_color: '#EEF1EC',
        display: 'standalone',
        orientation: 'portrait-primary',
        lang: 'pt-BR',
        start_url: '/',
        icons: [
          {
            src: '/favicon.ico',
            sizes: '64x64 32x32 24x24 16x16',
            type: 'image/x-icon'
          }
        ]
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,ico,woff2}'],
        navigateFallback: '/index.html',
        navigateFallbackDenylist: [/^\/api\//, /^\/cotacoes-/, /^\/proxy-cidades/, /^\/webhooks\//]
      }
    })
  ],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: API_TARGET,
        changeOrigin: true
      },
      '/cotacoes-regionais': {
        target: API_TARGET,
        changeOrigin: true
      },
      '/cotacoes-brasil': {
        target: API_TARGET,
        changeOrigin: true
      },
      '/proxy-cidades': {
        target: API_TARGET,
        changeOrigin: true
      }
    }
  }
});
