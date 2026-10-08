/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./desktop/renderer/**/*.{ts,tsx,html}",
  ],
  theme: {
    extend: {
      colors: {
        overlay: {
          bg: "rgba(10, 10, 15, 0.88)",
          border: "rgba(255, 255, 255, 0.08)",
          text: "#e8eaf0",
          muted: "#8892a4",
          accent: "#4f9cf9",
          success: "#34d399",
          warning: "#fbbf24",
          error: "#f87171",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Consolas", "monospace"],
      },
      backdropBlur: {
        xs: "2px",
      },
    },
  },
  plugins: [],
};
