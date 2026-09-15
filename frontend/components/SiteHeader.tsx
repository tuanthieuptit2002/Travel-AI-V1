import Link from "next/link";

const links = [
  { href: "/", label: "Trang chủ" },
  { href: "/plan", label: "Lên kế hoạch" },
  { href: "/trips", label: "Chuyến đi" },
  { href: "/preferences", label: "Sở thích" },
];

type SiteHeaderProps = {
  active?: "home" | "plan" | "trips" | "preferences";
};

export function SiteHeader({ active }: SiteHeaderProps) {
  return (
    <header className="border-b border-tide/10 bg-foam/70 backdrop-blur-sm">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-4">
        <Link href="/" className="font-display text-xl text-tide">
          TripMind AI
        </Link>
        <nav className="flex items-center gap-1 sm:gap-2">
          {links.map((link) => {
            const isActive =
              (active === "home" && link.href === "/") ||
              (active === "plan" && link.href === "/plan") ||
              (active === "trips" && link.href.startsWith("/trips")) ||
              (active === "preferences" && link.href === "/preferences");
            return (
              <Link
                key={link.href}
                href={link.href}
                className={[
                  "rounded-full px-3 py-1.5 text-sm transition",
                  isActive ? "bg-tide text-foam" : "text-tide/70 hover:bg-mist hover:text-tide",
                ].join(" ")}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
