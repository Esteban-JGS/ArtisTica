/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,jsx,ts,tsx}'],
  presets: [require('nativewind/preset')],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: '#201d1a',
          700: '#3d362f',
          600: '#4a423a',
        },
        accent: {
          DEFAULT: '#c2653b',
          dark: '#a1512d',
          darker: '#ae5731',
        },
        sand: {
          50: '#fdf8f3',
          100: '#f7f5f1',
          200: '#efece7',
          300: '#e2ddd5',
        },
        stone: {
          400: '#a49a90',
          500: '#9b9187',
          600: '#948b82',
          700: '#8b8279',
          800: '#7f766d',
          900: '#5c534b',
        },
        gold: '#d99a3f',
        sage: '#3f6b63',
      },
      fontFamily: {
        serif: ['InstrumentSerif_400Regular', 'Georgia', 'serif'],
      },
    },
  },
  plugins: [],
};
