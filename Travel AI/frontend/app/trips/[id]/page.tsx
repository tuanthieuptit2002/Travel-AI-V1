import { redirect } from "next/navigation";

type TripDetailPageProps = {
  params: Promise<{ id: string }>;
};

/** Legacy route: saved trips now have short root-level URLs. */
export default async function TripDetailPage({ params }: TripDetailPageProps) {
  const { id } = await params;
  redirect(`/${encodeURIComponent(id)}`);
}
