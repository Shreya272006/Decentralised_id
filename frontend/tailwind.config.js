/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#f0f5ff",
          100: "#dbe6ff",
          200: "#b8cdff",
          300: "#8aa9ff",
          400: "#5c7fff",
          500: "#3a58f5",
          600: "#2a3fd6",
          700: "#2231ab",
          800: "#202b85",
          900: "#1e2769",
        },
      },
      borderRadius: {
        xl2: "1.25rem",
      },
    },
  },
  plugins: [],
};
