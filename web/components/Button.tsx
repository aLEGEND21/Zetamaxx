import type { ButtonHTMLAttributes } from "react";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" | "danger" };

const STYLES = {
  primary: "bg-text text-surface hover:bg-black border border-text",
  secondary: "bg-surface text-text border border-border hover:border-muted",
  ghost: "text-muted hover:text-text border border-transparent",
  danger: "bg-surface text-danger border border-border hover:border-danger",
};

/** The button look as a class string, for links that should look like buttons. */
export function buttonClass(variant: keyof typeof STYLES = "secondary", className = ""): string {
  return `inline-flex h-10 items-center justify-center gap-2 rounded-lg px-4 text-sm font-medium transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-50 ${STYLES[variant]} ${className}`;
}

export function Button({ variant = "secondary", className = "", type = "button", ...rest }: Props) {
  return <button type={type} className={buttonClass(variant, className)} {...rest} />;
}
