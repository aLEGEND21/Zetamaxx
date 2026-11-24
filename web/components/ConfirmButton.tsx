"use client";

import { useState, type ReactNode } from "react";
import { Button } from "./Button";

type Props = {
  children: ReactNode;
  /** Shown next to the confirm button, e.g. "The old link will stop working." */
  warning: string;
  confirmLabel: string;
  onConfirm: () => void;
  disabled?: boolean;
  variant?: "secondary" | "ghost" | "danger";
};

/** A button for actions that can't be undone: the first click asks, the second acts. */
export function ConfirmButton({ children, warning, confirmLabel, onConfirm, disabled, variant = "secondary" }: Props) {
  const [asking, setAsking] = useState(false);
  if (!asking) {
    return (
      <Button variant={variant} disabled={disabled} onClick={() => setAsking(true)}>
        {children}
      </Button>
    );
  }
  return (
    <span className="inline-flex flex-wrap items-center gap-2" role="group" aria-label={warning}>
      <span className="text-xs text-muted">{warning}</span>
      <Button
        variant="danger"
        autoFocus
        disabled={disabled}
        onClick={() => {
          setAsking(false);
          onConfirm();
        }}
      >
        {confirmLabel}
      </Button>
      <Button variant="ghost" onClick={() => setAsking(false)}>
        Cancel
      </Button>
    </span>
  );
}
