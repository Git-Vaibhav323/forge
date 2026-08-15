import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#F3F0E8",
        panel: "#FBFAF6",
        ink: "#15161A",
        muted: "#6B6960",
        faint: "#9C998E",
        line: "#DEDBD1",
        "line-strong": "#C7C3B6",
        accent: {
          DEFAULT: "#1F5AA6",
          soft: "#E6EEF7",
        },
        verified: {
          DEFAULT: "#2F6E4E",
          soft: "#E4EFE8",
        },
        review: {
          DEFAULT: "#A75A0A",
          soft: "#F5E9D9",
        },
        conflict: {
          DEFAULT: "#9A2E2E",
          soft: "#F3E1E1",
        },
        missing: {
          DEFAULT: "#6B6960",
          soft: "#EDECE7",
        },
      },
      fontFamily: {
        sans: ["var(--font-plex-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-plex-mono)", "ui-monospace", "monospace"],
      },
      borderRadius: {
        none: "0px",
        sm: "2px",
        DEFAULT: "3px",
        md: "4px",
      },
      boxShadow: {
        panel: "none",
      },
    },
  },
  plugins: [],
};
export default config;
