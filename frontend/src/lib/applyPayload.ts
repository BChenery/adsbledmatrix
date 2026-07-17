import { Layout } from '@/types/layout';

/** Payload for POST /api/display/apply-layout — pushes a layout to the matrix without saving. */
export function applyPayload(layout: Layout) {
  return {
    name: layout.name,
    width: layout.width,
    height: layout.height,
    elements: layout.elements.map((el) => ({
      element_type: el.element_type,
      x: el.x,
      y: el.y,
      width: el.width,
      height: el.height,
      z_index: el.z_index ?? 0,
      font_family: el.font_family,
      font_size: el.font_size,
      color: el.color,
      bg_color: el.bg_color,
      format_str: el.format_str,
      data_field: el.data_field,
      image_path: el.image_path,
      image_url: el.image_url,
      show_if: el.show_if,
      extra: el.extra,
      range_km: el.range_km,
      ring_color: el.ring_color,
      dot_color: el.dot_color,
      user_dot_color: el.user_dot_color,
      show_rings: el.show_rings,
      show_ticks: el.show_ticks,
      use_plane_symbol: el.use_plane_symbol,
    })),
  };
}
