import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "TripMind AI | Lên kế hoạch du lịch Việt Nam thông minh",
  description: "Lên kế hoạch chuyến đi Việt Nam với trợ lý AI dựa trên dữ liệu thực.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="vi">
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
