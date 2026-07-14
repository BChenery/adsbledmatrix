export interface ChangelogSection {
  title: string;
  items: string[];
}

export interface ChangelogEntry {
  version: string;
  date?: string | null;
  sections: ChangelogSection[];
}

export interface ChangelogResponse {
  current_version: string;
  entries: ChangelogEntry[];
}
