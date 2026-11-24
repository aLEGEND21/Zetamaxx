import { SignUp } from "@clerk/nextjs";
import { Suspense } from "react";

// Clerk's component reads the request, so with Cache Components it renders inside Suspense.
export default function SignUpPage() {
  return (
    <main className="flex flex-1 items-center justify-center px-4 py-12">
      <Suspense fallback={<div className="h-96 w-full max-w-sm animate-pulse rounded-card bg-border/60" />}>
        <SignUp />
      </Suspense>
    </main>
  );
}
