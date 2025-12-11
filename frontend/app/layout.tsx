import Sidebar from "@/components/Sidebar";
import "./globals.css";

export const metadata = {
  title: "CARTMIND-AI - Smart Checkout Automation",
  description: "AI-powered checkout automation system",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <div className="flex h-screen bg-background">
          <Sidebar />
          <main className="flex-1 overflow-auto">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
