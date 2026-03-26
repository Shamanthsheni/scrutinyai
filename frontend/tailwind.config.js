/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        navy: '#0f2238',
        teal: {
          DEFAULT: '#0f6e56',
          light: '#e1f5ee',
          dark: '#085041',
        },
        'amber-custom': {
          DEFAULT: '#854f0b',
          light: '#faeeda',
        },
        'red-custom': {
          DEFAULT: '#a32d2d',
          light: '#fcebeb',
        },
        slate: '#94a3b8',
        'gray-text': '#5f5e5a',
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
