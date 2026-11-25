// Next.js 16 calls the middleware file `proxy.ts`.
//
// Signed-out visitors to the pages in app/(private) are sent to /sign-in and
// returned to the page they asked for afterwards. This is a convenience, not
// the security boundary: these pages contain no data of their own, and every
// API call is verified by FastAPI (api/app/auth.py).
//
// While a feature is switched off (lib/features.ts), its pages answer 404:
// friends and groups, and /settings, which holds only the custom-mode form.
import { clerkMiddleware } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import { CUSTOM_MODE, SOCIAL } from "@/lib/features";

const SIGNED_IN_ONLY = ["/friends", "/groups"];
const SOCIAL_PAGES = ["/friends", "/groups", "/join"];
const CUSTOM_MODE_PAGES = ["/settings"];

function under(paths: string[], pathname: string): boolean {
  return paths.some((path) => pathname === path || pathname.startsWith(`${path}/`));
}

export default clerkMiddleware(async (auth, request) => {
  const { pathname } = request.nextUrl;
  if ((!SOCIAL && under(SOCIAL_PAGES, pathname)) || (!CUSTOM_MODE && under(CUSTOM_MODE_PAGES, pathname))) {
    // No route is called /404, so this renders the normal "not found" page with a 404 status.
    return NextResponse.rewrite(new URL("/404", request.url));
  }
  if (under(SIGNED_IN_ONLY, pathname)) await auth.protect();
});

export const config = {
  // Skip Next.js internals, static files, and /api (FastAPI verifies tokens itself).
  matcher: ["/((?!_next|api|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)"],
};
