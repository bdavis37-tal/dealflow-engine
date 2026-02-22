import type { Config } from 'tailwindcss'

const config: Config = {
  darkMode: 'class',
  content: [
    './index.html',
    './src/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // Brand colors
        navy: {
          900: '#0a0f1e',
          800: '#0d1526',
          700: '#111d35',
          600: '#162444',
        },
        slate: {
          850: '#1a2235',
          900: '#0f172a',
        },
        // Semantic colors — used only on meaningful metrics
        success: '#22c55e',   // Accretive / positive
        danger:  '#ef4444',   // Dilutive / negative
        caution: '#f59e0b',   // Marginal / warning
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      fontSize: {
        '2xs': '0.625rem',
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.4s ease-out',
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      backgroundImage: {
        'green-glow': 'radial-gradient(ellipse at center, rgba(34,197,94,0.08) 0%, transparent 70%)',
        'red-glow': 'radial-gradient(ellipse at center, rgba(239,68,68,0.08) 0%, transparent 70%)',
        'amber-glow': 'radial-gradient(ellipse at center, rgba(245,158,11,0.08) 0%, transparent 70%)',
      },
    },
  },
  plugins: [],
}

export default config
