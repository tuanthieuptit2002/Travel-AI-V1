import { redirect } from "next/navigation";

/** Legacy route: saved trips now open in a drawer on the single landing page. */
export default function TripsPage() {
  redirect("/?panel=trips");
}
