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
      <CardHeader>
        <CardTitle className="text-sm text-white/70 flex items-center gap-2">
          {Icon && <Icon size={14} />}
          {title}
        </CardTitle>
        {description && (
          <p className="text-xs text-white/50 leading-relaxed">{description}</p>
        )}
      </CardHeader>
      <CardContent className="space-y-4">{children}</CardContent>
    </Card>
  );
}
