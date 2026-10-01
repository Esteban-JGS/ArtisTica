const { colors } = require('./src/theme/colors');

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,jsx,ts,tsx}'],
  presets: [require('nativewind/preset')],
  theme: {
    extend: {
      colors,
      fontFamily: {
        serif: ['InstrumentSerif_400Regular', 'Georgia', 'serif'],
      },
    },
  },
  plugins: [],
};
