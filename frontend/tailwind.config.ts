import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      boxShadow: {
        crisp: "0 1px 0 rgba(24, 24, 27, 0.08)",
      },
    },
  },
  plugins: [],
} satisfies Config;

