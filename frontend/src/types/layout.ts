export type ElementType =
  | 'text'
  | 'data_field'
  | 'image'
  | 'shape'
  | 'heading_arrow'
  | 'vertical_rate'
  | 'distance_bar'
  | 'radar_blip'
  | 'aircraft_list';

export interface LayoutElement {
  id?: number;
  element_type: ElementType;
  x: number;
  y: number;
  width?: number;
  height?: number;
  z_index: number;
  font_family?: string;
  font_size?: number;
  color?: string;
  bg_color?: string;
  format_str?: string;
  data_field?: string;
  image_path?: string;
  image_url?: string;
  show_if?: string;
  extra?: Record<string, unknown>;
}

export interface Layout {
  id?: number;
  name: string;
  description?: string;
  width: number;
  height: number;
  is_default: boolean;
  elements: LayoutElement[];
  created_at?: string;
  updated_at?: string;
}
