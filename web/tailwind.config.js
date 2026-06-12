/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      colors: {
        ink: {
          950: "#0a0e1a",
          900: "#0f1424",
          850: "#141a2e",
          800: "#1a2138",
          700: "#252e4a",
          600: "#384266",
        },
        verdict: {
          valid: "#f04747",
          review: "#f6a821",
          fp: "#28c76f",
          unclear: "#7a8aa8",
        },
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.4s ease-out",
      },
    },
  },
  plugins: [],
};
