import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Same VITE_AWS_API_BASE_URL the app code reads via import.meta.env --
  // loaded here too so the dev-server proxy target isn't a second,
  // independently-hardcoded copy of the URL.
  const env = loadEnv(mode, process.cwd(), '')
  const awsApiBaseUrl = env.VITE_AWS_API_BASE_URL

  return {
    plugins: [react()],
    server: {
      proxy: {
        '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
        '/ws': { target: 'ws://127.0.0.1:8000', ws: true },
        // The deployed AWS API has no CORS headers configured (see
        // infra/template.yaml), so a browser can't call it directly.
        // Proxying it through the dev server keeps the browser's request
        // same-origin; the dev server's own server-to-server request to
        // AWS isn't subject to CORS at all.
        ...(awsApiBaseUrl
          ? {
              '/aws-api': {
                target: awsApiBaseUrl,
                changeOrigin: true,
                rewrite: (path: string) => path.replace(/^\/aws-api/, ''),
              },
            }
          : {}),
      },
    },
  }
})
