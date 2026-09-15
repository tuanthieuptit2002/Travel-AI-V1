import { SiteHeader } from "../components/SiteHeader";
import { HomePlanForm } from "../components/HomePlanForm";

export default function HomePage() {
  return (
    <div className="min-h-screen bg-[linear-gradient(165deg,#f7fcfa_0%,#dceee8_52%,#c8dfd8_100%)] text-ink">
      <SiteHeader active="home" />
      <main className="mx-auto grid max-w-6xl gap-10 px-6 py-12 lg:grid-cols-[1.05fr_0.95fr] lg:items-center lg:py-16">
        <section>
          <p className="text-sm font-semibold uppercase tracking-[0.28em] text-lagoon">TripMind AI</p>
          <h1 className="mt-4 max-w-xl font-display text-5xl leading-[1.05] tracking-tight text-tide sm:text-6xl">
            Lên kế hoạch chuyến đi hoàn hảo với AI
          </h1>
          <p className="mt-5 max-w-lg text-base leading-7 text-ink/70">
            Bắt đầu bằng ngôn ngữ tự nhiên. Thêm điểm đi, ngày tháng, ngân sách, sở thích và nhịp độ nếu
            muốn. TripMind lấy địa điểm, nhà hàng và thời tiết từ API thực.
          </p>
        </section>
        <HomePlanForm />
      </main>
    </div>
  );
}
