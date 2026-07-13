import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import type { LucideIcon } from 'lucide-react';

export interface SettingsSectionProps {
  title: string;
  icon?: LucideIcon;
  description?: string;
  children: React.ReactNode;
  className?: string;
}

export default function SettingsSection({
  title,
  icon: Icon,
  description,
  children,
  className,
}: SettingsSectionProps) {
  return (
    <Card className={cn(className)}>
      <CardHeader className="space-y-2">
        <CardTitle className="flex items-center gap-2 text-[13px] font-medium text-led-dim">
          {Icon && (
            <span className="flex h-7 w-7 items-center justify-center rounded-lg border border-led-line bg-led-panel text-led-accent">
              <Icon size={14} />
            </span>
          )}
          <span className="font-display tracking-tight text-[#f5f5f5]">{title}</span>
        </CardTitle>
        {description && (
          <p className="text-xs leading-relaxed text-led-faint sm:text-[13px]">{description}</p>
        )}
      </CardHeader>
      <CardContent className="space-y-4">{children}</CardContent>
    </Card>
  );
}
