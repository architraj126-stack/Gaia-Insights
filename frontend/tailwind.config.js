/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        background: {
          DEFAULT: '#0b0f19', // Dark navy / deep charcoal
          elevated: '#111827',
          card: '#162032',
          surface: '#1e293b',
        },
        border: {
          subtle: '#26334a',
          DEFAULT: '#334155',
          active: '#3b82f6',
        },
        navy: {
          950: '#070a12',
          900: '#0b0f19',
          850: '#111827',
          800: '#162032',
          700: '#1e293b',
          600: '#334155',
        },
        accent: {
          blue: '#3b82f6',      // Clear blue accent
          'blue-hover': '#2563eb',
          cyan: '#06b6d4',      // Clear cyan accent
          'cyan-hover': '#0891b2',
        },
        status: {
          available: '#10b981',
          partial: '#f59e0b',
          unavailable: '#64748b',
          loading: '#3b82f6',
          failed: '#ef4444',
          needsValidation: '#8b5cf6',
        }
      },
      borderRadius: {
        'card': '0.75rem',
      },
      boxShadow: {
        'card': '0 4px 6px -1px rgba(0, 0, 0, 0.3), 0 2px 4px -2px rgba(0, 0, 0, 0.2)',
        'elevated': '0 10px 15px -3px rgba(0, 0, 0, 0.4), 0 4px 6px -4px rgba(0, 0, 0, 0.3)',
      }
    },
  },
  plugins: [],
}
