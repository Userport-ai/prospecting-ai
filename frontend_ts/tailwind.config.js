/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  // Default theme: in case we ever need to go back.
  //   theme: {
  //   	extend: {
  //   		fontFamily: {
  //   			inter: [
  //   				'Inter',
  //   				'sans-serif'
  //   			]
  //   		},
  //   		borderRadius: {
  //   			lg: 'var(--radius)',
  //   			md: 'calc(var(--radius) - 2px)',
  //   			sm: 'calc(var(--radius) - 4px)'
  //   		},
  //   		colors: {
  //   			background: 'hsl(var(--background))',
  //   			foreground: 'hsl(var(--foreground))',
  //   			card: {
  //   				DEFAULT: 'hsl(var(--card))',
  //   				foreground: 'hsl(var(--card-foreground))'
  //   			},
  //   			popover: {
  //   				DEFAULT: 'hsl(var(--popover))',
  //   				foreground: 'hsl(var(--popover-foreground))'
  //   			},
  //   			primary: {
  //   				DEFAULT: 'hsl(var(--primary))',
  //   				foreground: 'hsl(var(--primary-foreground))'
  //   			},
  //   			secondary: {
  //   				DEFAULT: 'hsl(var(--secondary))',
  //   				foreground: 'hsl(var(--secondary-foreground))'
  //   			},
  //   			muted: {
  //   				DEFAULT: 'hsl(var(--muted))',
  //   				foreground: 'hsl(var(--muted-foreground))'
  //   			},
  //   			accent: {
  //   				DEFAULT: 'hsl(var(--accent))',
  //   				foreground: 'hsl(var(--accent-foreground))'
  //   			},
  //   			destructive: {
  //   				DEFAULT: 'hsl(var(--destructive))',
  //   				foreground: 'hsl(var(--destructive-foreground))'
  //   			},
  //   			border: 'hsl(var(--border))',
  //   			input: 'hsl(var(--input))',
  //   			ring: 'hsl(var(--ring))',
  //   			chart: {
  //   				'1': 'hsl(var(--chart-1))',
  //   				'2': 'hsl(var(--chart-2))',
  //   				'3': 'hsl(var(--chart-3))',
  //   				'4': 'hsl(var(--chart-4))',
  //   				'5': 'hsl(var(--chart-5))'
  //   			},
  //   			sidebar: {
  //   				DEFAULT: 'hsl(var(--sidebar-background))',
  //   				foreground: 'hsl(var(--sidebar-foreground))',
  //   				primary: 'hsl(var(--sidebar-primary))',
  //   				'primary-foreground': 'hsl(var(--sidebar-primary-foreground))',
  //   				accent: 'hsl(var(--sidebar-accent))',
  //   				'accent-foreground': 'hsl(var(--sidebar-accent-foreground))',
  //   				border: 'hsl(var(--sidebar-border))',
  //   				ring: 'hsl(var(--sidebar-ring))'
  //   			}
  //   		}
  //   	}
  //   },
  //   plugins: [require("tailwindcss-animate")],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "sans-serif"],
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        card: {
          DEFAULT: "var(--card)",
          foreground: "var(--card-foreground)",
        },
        popover: {
          DEFAULT: "var(--popover)",
          foreground: "var(--popover-foreground)",
        },
        primary: {
          DEFAULT: "var(--primary)",
          foreground: "var(--primary-foreground)",
        },
        secondary: {
          DEFAULT: "var(--secondary)",
          foreground: "var(--secondary-foreground))",
        },
        muted: {
          DEFAULT: "var(--muted)",
          foreground: "var(--muted-foreground)",
        },
        accent: {
          DEFAULT: "var(--accent)",
          foreground: "var(--accent-foreground)",
        },
        destructive: {
          DEFAULT: "var(--destructive)",
          foreground: "var(--destructive-foreground)",
        },
        border: "var(--border)",
        input: "var(--input)",
        ring: "var(--ring)",
        chart: {
          1: "var(--chart-1)",
          2: "var(--chart-2)",
          3: "var(--chart-3)",
          4: "var(--chart-4)",
          5: "var(--chart-5)",
        },
        sidebar: {
          DEFAULT: "var(--sidebar-background)",
          foreground: "var(--sidebar-foreground)",
          primary: "var(--sidebar-primary)",
          "primary-foreground": "var(--sidebar-primary-foreground)",
          accent: "var(--sidebar-accent)",
          "accent-foreground": "var(--sidebar-accent-foreground)",
          border: "var(--sidebar-border)",
          ring: "var(--sidebar-ring)",
        },
      },
      keyframes: {
        "accordion-down": {
          from: {
            height: "0",
          },
          to: {
            height: "var(--radix-accordion-content-height)",
          },
        },
        "accordion-up": {
          from: {
            height: "var(--radix-accordion-content-height)",
          },
          to: {
            height: "0",
          },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
