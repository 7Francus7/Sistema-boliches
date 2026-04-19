/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts}'],
  theme: {
    extend: {
      colors: {
        // Paleta industrial de alto contraste — inspirada en POS antiguos
        'panel': '#0a0a0a',
        'panel-2': '#141414',
        'ink': '#f5f5f5',
        'dim': '#9a9a9a',
        'hot': '#f59e0b',       // ámbar industrial
        'danger': '#dc2626',
        'ok': '#16a34a',
        'line': '#2a2a2a',
      },
      fontFamily: {
        mono: ['"JetBrains Mono"', '"Courier New"', 'monospace'],
        display: ['"Arial Black"', 'Arial', 'sans-serif'],
      },
      fontSize: {
        // Base 18px — textos grandes para leer a oscuras bajo presión
        'xs': '14px',
        'sm': '16px',
        'base': '18px',
        'lg': '22px',
        'xl': '28px',
        '2xl': '36px',
        '3xl': '48px',
        '4xl': '64px',
      },
      borderRadius: {
        'none': '0',
        DEFAULT: '0',
      },
    },
  },
  plugins: [],
  corePlugins: {
    // Nada de animaciones ni transiciones. Cero frills.
    animation: false,
    transitionProperty: false,
  },
}
