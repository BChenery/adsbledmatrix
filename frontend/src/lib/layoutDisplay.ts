import { Aircraft } from '@/types/aircraft';
import { LayoutElement } from '@/types/layout';

export function getAircraftDisplayValue(ac: Aircraft | undefined, el: LayoutElement): string {
  if (!ac) return '';

  if (el.element_type === 'data_field') {
    let template = el.format_str || `{${el.data_field}}`;
    return template.replace(/\{(\w+)\}/g, (_, key) => {
      if (key === 'distance' && ac.distance_km != null) {
        return ac.distance_display || `${ac.distance_km.toFixed(1)} km`;
      }
      const val = ac[key as keyof Aircraft];
      if (val !== undefined && val !== null) return String(val);
      // Route-related fields show a placeholder instead of blank when missing
      if (['route', 'origin', 'destination'].includes(key)) return '---';
      return '';
    });
  }

  if (el.element_type === 'vertical_rate') {
    const vr = ac.vertical_rate;
    if (vr === undefined) return '▲ 1200';
    return `${vr > 0 ? '▲' : '▼'} ${Math.abs(vr)}`;
  }

  if (el.element_type === 'distance_bar') {
    const dist = ac.distance_km;
    if (dist === undefined) return '|||||';
    const bars = Math.min(10, Math.max(1, Math.round(dist)));
    return '█'.repeat(bars);
  }

  if (el.element_type === 'heading_arrow') {
    const heading = ac.heading;
    if (heading === undefined) return '→';
    const arrows = ['→', '↘', '↓', '↙', '←', '↖', '↑', '↗'];
    const idx = Math.round(heading / 45) % 8;
    return arrows[idx];
  }

  return '';
}
