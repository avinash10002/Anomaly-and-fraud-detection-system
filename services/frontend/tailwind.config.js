/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "#1a2332",
          muted: "#5c6b7a",
          faint: "#8a97a5",
        },
        surface: {
          DEFAULT: "#f4f6f8",
          card: "#ffffff",
          soft: "#e8edf2",
        },
        brand: {
          DEFAULT: "#1b4f72",
          dark: "#0e2f46",
        },
        risk: {
          low: "#1e7a46",
          mid: "#b8860b",
          high: "#c0392b",
        },
      },
      fontFamily: {
        sans: ["var(--font-source-sans)", "Segoe UI", "system-ui", "sans-serif"],
        display: ["var(--font-ibm-plex)", "Segoe UI", "system-ui", "sans-serif"],
      },
      boxShadow: {
        panel: "0 1px 2px rgba(26, 35, 50, 0.06), 0 8px 24px rgba(26, 35, 50, 0.06)",
      },
    },
  },
  plugins: [],
};
