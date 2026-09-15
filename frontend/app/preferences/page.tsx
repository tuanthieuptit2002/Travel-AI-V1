import { SiteHeader } from "../../components/SiteHeader";
import { PreferencesPanel } from "../../components/PreferencesPanel";

export default function PreferencesPage() {
  return (
    <div className="min-h-screen bg-[linear-gradient(165deg,#f7fcfa_0%,#dceee8_52%,#c8dfd8_100%)] text-ink">
      <SiteHeader active="preferences" />
      <main className="mx-auto max-w-3xl px-6 py-12">
        <PreferencesPanel />
      </main>
    </div>
  );
}
