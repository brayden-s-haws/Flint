/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
      './templates/**/*.html',
      './apps/**/templates/**/*.html',
  ],
  theme: {
      extend: {
          colors: {
              'flint': {
                  'bg':           '#0D0D0D',
                  'surface':      '#1A1A1A',
                  'card':         '#2A2A2A',
                  'text':         '#E6E6E6',
                  'muted':        '#9A9A9A',
                  'subtle':       '#6A6A6A',
                  'orange':       '#FF4F00',
                  'orange-hover': '#E64700',
                  'border':       '#2A2A2A',
                  'border-em':    '#3A3A3A',
                  'success':      '#00BA88',
              }
          },
          fontFamily: {
              sans: ['Geist', 'Inter', 'sans-serif'],
          }
      }
  },
  plugins: [],
}

