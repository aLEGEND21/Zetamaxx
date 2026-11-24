// Makes Clerk's components match the app: light, near-monochrome, 1px borders.
export const clerkAppearance = {
  variables: {
    colorPrimary: "#111111",
    colorForeground: "#111111",
    colorMutedForeground: "#6b6b6b",
    colorBackground: "#ffffff",
    colorBorder: "#e5e5e5",
    colorDanger: "#b42318",
    borderRadius: "10px",
    fontFamily: "var(--font-inter), ui-sans-serif, system-ui, sans-serif",
  },
  elements: {
    cardBox: { boxShadow: "none", border: "1px solid #e5e5e5" },
    card: { boxShadow: "none" },
  },
};
