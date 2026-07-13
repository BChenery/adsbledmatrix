import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-medium tracking-tight transition-colors focus:outline-none focus:ring-2 focus:ring-led-accent/40 focus:ring-offset-2 focus:ring-offset-led-black",
  {
    variants: {
      variant: {
        default:
          "border-led-accent/25 bg-led-accent/10 text-led-accent",
        secondary:
          "border-led-line bg-led-panel text-led-dim",
        destructive:
          "border-led-red/25 bg-led-red/10 text-led-red",
        outline: "border-led-line text-led-dim",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

export { Badge, badgeVariants }
