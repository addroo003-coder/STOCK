import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "장성혁 자문역의 투자 LAB",
  description: "AI 반도체·로봇·바이오·AI 인프라 및 전력을 시나리오별로 비교하는 투자판단 대시보드",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
