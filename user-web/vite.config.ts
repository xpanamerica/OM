import { defineConfig, loadEnv } from "vite";
import vue from "@vitejs/plugin-vue";
import { fileURLToPath, URL } from "node:url";
import Components from "unplugin-vue-components/vite";
import { ElementPlusResolver } from "unplugin-vue-components/resolvers";

function apiOriginForPreconnect(apiBase: string): string | null {
  const u = apiBase.trim().replace(/\/$/, "");
  if (!u || u.startsWith("/")) return null;
  try {
    return new URL(u).origin;
  } catch {
    return null;
  }
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiOrigin = apiOriginForPreconnect(env.VITE_API_BASE_URL ?? "");

  return {
  plugins: [
    vue(),
    Components({
      resolvers: [
        ElementPlusResolver({
          importStyle: "css",
        }),
      ],
    }),
    ...(apiOrigin
      ? [
          {
            name: "html-inject-api-preconnect",
            transformIndexHtml(html: string) {
              const links = `    <link rel="preconnect" href="${apiOrigin}" crossorigin />\n    <link rel="dns-prefetch" href="${apiOrigin}" />`;
              return html.replace("</head>", `${links}\n  </head>`);
            },
          },
        ]
      : []),
  ],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    port: 5173,
  },
  build: {
    target: "es2022",
    reportCompressedSize: false,
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return;
          if (id.includes("element-plus")) return "element-plus";
          if (id.includes("axios")) return "axios";
          if (id.includes("ali-oss")) return "ali-oss";
          if (
            id.includes("vue-router") ||
            id.includes("pinia") ||
            id.includes("/vue/") ||
            id.includes("@vue/")
          ) {
            return "vue-vendor";
          }
        },
      },
    },
  },
};
});
