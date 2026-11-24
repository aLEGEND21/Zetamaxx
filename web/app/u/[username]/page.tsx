import { Suspense } from "react";
import { ProfileSkeleton } from "@/components/Skeleton";
import { ProfileView } from "@/components/views/ProfileView";

export const metadata = { title: "Profile · Zetamaxx" };

// The username is only known at request time, so the view that reads it renders inside Suspense.
export default function ProfilePage() {
  return (
    <Suspense fallback={<ProfileSkeleton />}>
      <ProfileView />
    </Suspense>
  );
}
