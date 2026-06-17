import './globals.css';

export const metadata = {
  title: 'World Cup Prediction Platform',
  description: '可解釋、可追蹤的世界盃足球預測平台'
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-Hant">
      <body>{children}</body>
    </html>
  );
}
