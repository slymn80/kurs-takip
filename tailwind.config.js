/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/templates/**/*.html",
    "./app/static/js/**/*.js"
  ],
  theme: {
    extend: {
      fontFamily: {
        display: ["DM Serif Display", "serif"],
        sans: ["IBM Plex Sans", "system-ui", "sans-serif"]
      },
      colors: {
        ink: {
          50: "#f6f2e9",
          100: "#efe7db",
          200: "#ddd1c0",
          300: "#c2b3a0",
          400: "#9d8b77",
          500: "#7d6a58",
          600: "#635243",
          700: "#3f4f63",
          800: "#2d3b4d",
          900: "#1f2a36"
        },
        accent: {
          400: "#2f8f6b",
          500: "#1f6f53",
          600: "#195b45"
        }
      }
    }
  },
  plugins: []
};
