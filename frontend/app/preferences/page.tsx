import { redirect } from "next/navigation";

/** Legacy route: travel preferences now open in a drawer on the landing page. */
export default function PreferencesPage() {
  redirect("/?panel=preferences");
}
