import { redirect } from "next/navigation";

type TripDetailPageProps = {
  params: Promise<{ id: string }>;
};

/** Legacy route: the trip is rendered inline in the landing page conversation. */
export default async function TripDetailPage({ params }: TripDetailPageProps) {
  const { id } = await params;
  redirect(`/?trip=${encodeURIComponent(id)}`);
}
