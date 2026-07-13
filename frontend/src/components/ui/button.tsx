import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full text-sm font-medium tracking-tight transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-led-accent/50 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0 active:scale-[0.98]",
  {
    variants: {
      variant: {
        default:
          "bg-[#f5f5f5] text-led-black shadow-sm hover:bg-white hover:-translate-y-px hover:shadow-[0_8px_20px_rgba(255,255,255,0.08)]",
        destructive:
          "bg-led-red/15 text-led-red border border-led-red/25 shadow-sm hover:bg-led-red/25",
        outline:
          "border border-led-line bg-transparent text-[#f5f5f5] shadow-sm hover:border-[#3a3a3a] hover:bg-white/[0.03]",
        secondary:
          "border border-led-line bg-led-panel text-[#f5f5f5] shadow-sm hover:border-[#3a3a3a] hover:bg-white/[0.04]",
        ghost: "text-led-dim hover:bg-white/[0.04] hover:text-[#f5f5f5]",
        link: "text-led-accent underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-5 py-2",
        sm: "h-8 rounded-full px-3.5 text-xs",
        lg: "h-11 rounded-full px-8",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
