import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#10241f",
        mist: "#e7f3ef",
        lagoon: "#0f766e",
        tide: "#134e4a",
        sand: "#d8c3a5",
        foam: "#f4fbf8",
        // Warm sunset accent — the counterpoint that keeps the teal system from
        // feeling monochrome (used sparingly: one accent per view).
        coral: {
          DEFAULT: "#f2663b",
          soft: "#ffede5",
        },
      },
      fontFamily: {
        display: ["var(--font-display)", "Georgia", "serif"],
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui"],
      },
      boxShadow: {
        soft: "0 1px 2px rgba(16,36,31,0.05), 0 8px 24px -12px rgba(16,36,31,0.12)",
        lift: "0 2px 4px rgba(16,36,31,0.06), 0 20px 44px -16px rgba(16,36,31,0.22)",
        pop: "0 4px 8px rgba(16,36,31,0.08), 0 32px 72px -20px rgba(16,36,31,0.32)",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "slide-in-right": {
          "0%": { transform: "translateX(100%)" },
          "100%": { transform: "translateX(0)" },
        },
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "drift-a": {
          "0%, 100%": { transform: "translate3d(0, 0, 0) scale(1)" },
          "50%": { transform: "translate3d(4%, 6%, 0) scale(1.08)" },
        },
        "drift-b": {
          "0%, 100%": { transform: "translate3d(0, 0, 0) scale(1.05)" },
          "50%": { transform: "translate3d(-5%, -4%, 0) scale(1)" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.45s cubic-bezier(0.22, 1, 0.36, 1) both",
        "fade-in": "fade-in 0.25s ease-out both",
        "slide-in-right": "slide-in-right 0.32s cubic-bezier(0.22, 1, 0.36, 1) both",
        "drift-a": "drift-a 18s ease-in-out infinite",
        "drift-b": "drift-b 22s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
