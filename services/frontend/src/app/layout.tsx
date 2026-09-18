import type { Metadata } from "next";
import { IBM_Plex_Sans, Source_Sans_3 } from "next/font/google";
import { AppHeader } from "@/components/AppHeader";
import { RoleProvider } from "@/lib/role-context";
import "./globals.css";

const sourceSans = Source_Sans_3({
  subsets: ["latin"],
  variable: "--font-source-sans",
  display: "swap",
});

const ibmPlex = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  variable: "--font-ibm-plex",
  display: "swap",
});

export const metadata: Metadata = {
  title: "MPLAD Anomaly Detector",
  description:
    "Government dashboard for MPLAD fund utilisation anomaly detection.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${sourceSans.variable} ${ibmPlex.variable}`}>
      <body className="font-sans">
        <RoleProvider>
          <AppHeader />
          <main className="mx-auto min-h-[calc(100dvh-3.5rem)] max-w-7xl px-4 py-6 sm:px-6">
            {children}
          </main>
        </RoleProvider>
      </body>
    </html>
  );
}
