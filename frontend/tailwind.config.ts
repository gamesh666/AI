import type { Config } from "tailwindcss";

/**
 * Every color is a CSS variable (src/app/globals.css), so one DOM serves both themes:
 * <html data-theme="claude|tech">. Never add hex values here.
 */
const v = (name: string) => `var(--${name})`;

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: v("bg"),
        side: v("side"),
        panel: v("panel"),
        panel2: v("panel2"),
        line: v("line"),
        line2: v("line2"),
        ink: v("ink"),
        ink2: v("ink2"),
        muted: v("muted"),
        faint: v("faint"),
        accent: { DEFAULT: v("blue"), hi: v("blue-hi"), dim: v("blue-dim") },
        "on-accent": v("on-accent"),
        ok: { DEFAULT: v("ok"), dim: v("ok-dim") },
        warn: { DEFAULT: v("warn"), dim: v("warn-dim") },
        bad: { DEFAULT: v("bad"), dim: v("bad-dim") },
        sig: { ok: v("sig-ok"), warn: v("sig-warn"), bad: v("sig-bad"), idle: v("sig-idle") },
      },
      borderRadius: { card: "14px", panel: "16px", hero: "18px", item: "9px" },
      boxShadow: { card: v("shadow") },
      fontFamily: {
        sans: ["ui-sans-serif", "-apple-system", '"Segoe UI"', '"Noto Sans TC"', '"Microsoft JhengHei"', "system-ui", "sans-serif"],
        serif: ["Georgia", '"Times New Roman"', '"Noto Serif TC"', "serif"],
      },
      screens: { rail: "768px", wide: "1101px" },
    },
  },
  plugins: [],
};

export default config;
