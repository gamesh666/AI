import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef6ff",
          100: "#d9eaff",
          400: "#5aa2ff",
          500: "#2f7fff",
          600: "#1a63e6",
          700: "#154fb8",
        },
        surface: {
          900: "#0b0f17",
          800: "#111827",
          700: "#1a2233",
          600: "#243047",
        },
      },
    },
  },
  plugins: [],
};

export default config;
