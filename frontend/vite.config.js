import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
    plugins: [react()],
    build: {
        rollupOptions: {
            output: {
                manualChunks: function (id) {
                    if (id.indexOf("node_modules") === -1) {
                        return;
                    }
                    if (id.indexOf("react") !== -1 || id.indexOf("scheduler") !== -1) {
                        return "react-vendor";
                    }
                    if (id.indexOf("recharts") !== -1 || id.indexOf("d3-") !== -1) {
                        return "chart-vendor";
                    }
                },
            },
        },
    },
    server: {
        host: "0.0.0.0",
        port: 5173,
        proxy: {
            "/api": {
                target: "http://127.0.0.1:8000",
                changeOrigin: true,
            },
        },
    },
});
