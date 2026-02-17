/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/templates/**/*.html",
    "./app/static/js/**/*.js"
  ],
  theme: {
    extend: {
      fontFamily: {
        display: ["Fraunces", "serif"],
        sans: ["Manrope", "system-ui", "sans-serif"]
      },
      colors: {
        ink: {
          50: "#f4f2ed",
          100: "#ece6db",
          200: "#d8cdbb",
          300: "#bda98f",
          400: "#9a7f63",
          500: "#7b6148",
          600: "#5f4a36",
          700: "#3f4a5a",
          800: "#2c3b4d",
          900: "#1c2634"
        },
        accent: {
          400: "#2a8f7b",
          500: "#20715f",
          600: "#1b5a4c"
        }
      }
    }
  },
  plugins: []
};
