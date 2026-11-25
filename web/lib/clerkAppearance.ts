// Makes Clerk's components match the app: light, near-monochrome, 1px borders, no shadows.
// `variables` must be literal colours (Clerk derives shades from them); they mirror globals.css.
// `elements` are plain CSS, so they use the app's own variables.
const BORDER = "1px solid var(--border)";
const MENU_ROW = { padding: "10px 16px", gap: "12px" };
// Same width as the avatar above the rows, so the labels line up with the name.
const MENU_ICON = { flex: "0 0 36px" };

export const clerkAppearance = {
  variables: {
    colorPrimary: "#111111",
    colorForeground: "#111111",
    colorMutedForeground: "#6b6b6b",
    colorBackground: "#ffffff",
    // No colorBorder: Clerk draws borders at about 10% of it, so the default (black) gives the
    // app's light grey, while a light grey here makes every outline nearly invisible.
    colorDanger: "#b42318",
    borderRadius: "10px",
    fontFamily: "var(--font-inter), ui-sans-serif, system-ui, sans-serif",
  },
  elements: {
    // Sign-in, sign-up and the account window.
    cardBox: { boxShadow: "none", border: BORDER, borderRadius: "12px" },
    card: { boxShadow: "none" },
    // Clerk's default badge is nearly invisible with a black primary colour.
    badge: { color: "var(--muted)", border: BORDER, boxShadow: "none" },

    // The menu under the avatar in the header: a compact bordered card.
    userButtonPopoverCard: { width: "264px", boxShadow: "none", border: BORDER, borderRadius: "12px" },
    userButtonPopoverMain: { boxShadow: "none", borderRadius: 0 },
    userPreview: { padding: "14px 16px", gap: "12px" },
    userPreviewAvatarBox: { width: "36px", height: "36px" },
    userButtonPopoverActions: { borderTopColor: "var(--border)" },
    // Clerk's own rows (account, sign out) and ours (profile) are separate elements; style both alike.
    userButtonPopoverActionButton: MENU_ROW,
    userButtonPopoverCustomItemButton: MENU_ROW,
    userButtonPopoverActionButtonIconBox: MENU_ICON,
    userButtonPopoverCustomItemButtonIconBox: MENU_ICON,
    userButtonPopoverFooter: { borderTop: BORDER, background: "var(--bg)" },
  },
};

/**
 * The header's account button: avatar, @username and a chevron, so it reads as a menu.
 * Clerk renders only the avatar inside its button, so the other two are drawn with
 * pseudo-elements. Usernames are [a-z0-9_] only, which is safe inside a CSS string.
 */
export function accountButtonAppearance(username: string | undefined) {
  return {
    elements: {
      userButtonTrigger: {
        gap: "8px",
        height: "36px",
        padding: "0 8px",
        borderRadius: "8px",
        background: "transparent",
        color: "var(--text)",
        fontSize: "14px",
        fontWeight: 500,
        // No outline at rest; a faint fill shows it is a button on hover and while the menu is open.
        "&:hover, &[aria-expanded='true']": { background: "rgba(0, 0, 0, 0.05)" },
        "&::before": username ? { content: `"@${username}"`, order: 1 } : { content: "none" },
        "&::after": {
          content: '""',
          order: 2,
          width: "6px",
          height: "6px",
          marginTop: "-3px",
          borderRight: "1.5px solid var(--muted)",
          borderBottom: "1.5px solid var(--muted)",
          transform: "rotate(45deg)",
        },
      },
    },
  };
}

