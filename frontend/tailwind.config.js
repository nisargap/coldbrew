/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: "class",
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        base: "#09090B",
        surface: "#18181B",
        elevated: "#27272A",
        accent: {
          DEFAULT: "#3B82F6",
          hover: "#2563EB",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "sans-serif",
        ],
        mono: [
          "JetBrains Mono",
          "ui-monospace",
          "Cascadia Code",
          "Fira Code",
          "monospace",
        ],
      },
    },
  },
  plugins: [],
};
