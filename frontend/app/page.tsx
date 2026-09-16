import { Suspense } from "react";

import { ChatLanding } from "../components/ChatLanding";
import { ChatLandingSkeleton } from "../components/Skeleton";

export default function HomePage() {
  return (
    <Suspense fallback={<ChatLandingSkeleton />}>
      <ChatLanding />
    </Suspense>
  );
}
