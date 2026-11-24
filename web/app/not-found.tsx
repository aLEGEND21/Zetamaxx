import Link from "next/link";
import { buttonClass } from "@/components/Button";

export const metadata = { title: "Not found · Zetamaxx" };

export default function NotFound() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center px-4 py-16 text-center">
      <p className="nums text-6xl font-medium">404</p>
      <h1 className="mt-4 text-xl font-semibold">Nothing here</h1>
      <p className="mt-2 text-sm text-muted">That page doesn&apos;t exist. The numbers are still waiting, though.</p>
      <Link href="/" className={buttonClass("primary", "mt-6")}>
        Play
      </Link>
    </main>
  );
}
