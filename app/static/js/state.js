/* Shared UI state. One object, imported everywhere, so every screen sees the same values. */
export const state = {
  user: null,               // {email, name, role} or null
  project: null,            // full project object (always the whole line, unfiltered)
  projects: [],             // sidebar list
  equipment: [],            // equipment names for the downtime form
  selectedLocationId: null, // a Location id when a worksite child is selected, else null (whole line)
  expanded: new Set(),      // company line ids whose worksite children are expanded in the sidebar
};
