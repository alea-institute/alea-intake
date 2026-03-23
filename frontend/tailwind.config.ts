import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      spacing: {
        'xs': '4px',
        'sm-custom': '8px',
        'md-custom': '16px',
        'lg-custom': '24px',
        'xl-custom': '32px',
        '2xl-custom': '48px',
        '3xl-custom': '64px',
      },
    },
  },
  plugins: [],
} satisfies Config
