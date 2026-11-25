"use client";

import { ClerkLoading, Show, UserButton } from "@clerk/nextjs";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense } from "react";
import { accountButtonAppearance } from "@/lib/clerkAppearance";
import { CUSTOM_MODE, SOCIAL } from "@/lib/features";
import { useMe } from "@/lib/hooks";
import { Logo } from "./Logo";

function GearIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3h.1a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8v.1a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
    </svg>
  );
}

/** Same size and weight as the icons Clerk draws in the avatar menu. */
function PersonIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true">
      <circle cx="8" cy="5.25" r="2.5" />
      <path d="M3 13.5c.6-2.3 2.6-3.75 5-3.75s4.4 1.45 5 3.75" />
    </svg>
  );
}

/** Stands in for the account button while Clerk or the player's details are loading; same box, so nothing jumps. */
function AccountButtonSkeleton() {
  return (
    <span aria-hidden="true" className="flex h-9 items-center gap-2 px-2">
      <span className="h-7 w-7 animate-pulse rounded-full bg-border/60" />
      <span className="h-3 w-20 animate-pulse rounded bg-border/60" />
    </span>
  );
}

const NAV_LINK = "rounded-lg px-2.5 py-1.5 transition-colors duration-150 hover:text-text";

function ActiveNavLink({ href, children }: { href: string; children: React.ReactNode }) {
  const pathname = usePathname();
  const active = pathname === href || pathname.startsWith(`${href}/`);
  return (
    <Link href={href} aria-current={active ? "page" : undefined} className={`${NAV_LINK} ${active ? "text-text" : "text-muted"}`}>
      {children}
    </Link>
  );
}

// Reading the current path can suspend while a dynamic route prerenders, so the
// link renders plain first and gains its "current page" state once the path is known.
function NavLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Suspense
      fallback={
        <Link href={href} className={`${NAV_LINK} text-muted`}>
          {children}
        </Link>
      }
    >
      <ActiveNavLink href={href}>{children}</ActiveNavLink>
    </Suspense>
  );
}

export function Header() {
  const { me } = useMe();
  return (
    <header className="border-b border-border bg-bg">
      <div className="mx-auto flex h-14 w-full max-w-content items-center justify-between gap-2 px-4">
        <Link href="/" className="nums flex items-center gap-2 text-base font-semibold tracking-tight">
          <Logo />
          zetamaxx
        </Link>
        <nav className="flex items-center gap-0.5 text-sm" aria-label="Main">
          <Show when="signed-in">
            {SOCIAL && <NavLink href="/friends">Friends</NavLink>}
            {SOCIAL && <NavLink href="/groups">Groups</NavLink>}
          </Show>
          {CUSTOM_MODE && (
            <Link
              href="/settings"
              aria-label="Custom mode"
              title="Custom mode"
              className="flex h-9 w-9 items-center justify-center rounded-lg text-muted hover:text-text"
            >
              <GearIcon />
            </Link>
          )}
          <Show when="signed-in">
            <span className="ml-1.5 flex h-9 items-center">
              {/* The avatar menu is the signed-in navigation: profile, account, sign out. */}
              {me ? (
                <UserButton appearance={accountButtonAppearance(me.username)} fallback={<AccountButtonSkeleton />}>
                  <UserButton.MenuItems>
                    <UserButton.Link label="Profile" labelIcon={<PersonIcon />} href={`/u/${me.username}`} />
                    <UserButton.Action label="manageAccount" />
                    <UserButton.Action label="signOut" />
                  </UserButton.MenuItems>
                </UserButton>
              ) : (
                <AccountButtonSkeleton />
              )}
            </span>
          </Show>
          {/* Until Clerk has loaded, nobody knows whether the visitor is signed in. */}
          <ClerkLoading>
            <span className="ml-1.5 flex h-9 items-center">
              <AccountButtonSkeleton />
            </span>
          </ClerkLoading>
          <Show when="signed-out">
            <Link
              href="/sign-in"
              className="ml-1.5 rounded-lg border border-border bg-surface px-3 py-1.5 font-medium hover:border-muted"
            >
              Sign in
            </Link>
          </Show>
        </nav>
      </div>
    </header>
  );
}
