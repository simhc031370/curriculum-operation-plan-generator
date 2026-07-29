import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "교수학습평가 운영계획서 자동 생성",
  description:
    "학교급·학년·과목·총 시수를 입력하면 AI가 1학기 분량 운영계획서를 생성합니다.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
