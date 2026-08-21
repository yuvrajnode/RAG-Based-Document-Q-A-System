/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      colors: {
        ink: {
          50: "#f6f7f9",
          100: "#eceef2",
          200: "#d5d9e2",
          300: "#b0b8c9",
          400: "#8591aa",
          500: "#66738f",
          600: "#515c76",
          700: "#424b60",
          800: "#3a4052",
          900: "#181b23",
          950: "#0e1016",
        },
        accent: {
          50: "#eef4ff",
          100: "#dbe6ff",
          200: "#bed2ff",
          300: "#91b4ff",
          400: "#5d8bff",
          500: "#3763f6",
          600: "#2145e4",
          700: "#1b34bf",
          800: "#1c2f9c",
          900: "#1c2d7b",
        },
      },
      keyframes: {
        "fade-up": {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
      },
      animation: {
        "fade-up": "fade-up 220ms cubic-bezier(0.22, 1, 0.36, 1)",
        shimmer: "shimmer 1.6s linear infinite",
      },
    },
  },
  plugins: [],
};
