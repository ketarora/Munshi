import type { Metadata, Viewport } from "next";
import { Fraunces, IBM_Plex_Mono, Inter, Noto_Serif_Devanagari } from "next/font/google";
import "./globals.css";
import TopRail from "@/components/TopRail";
import SpatialBackgroundMount from "@/components/3d/SpatialBackgroundMount";

const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-display-var",
  display: "swap",
});

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-ui-var",
  display: "swap",
});

const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-mono-var",
  display: "swap",
});

const devanagari = Noto_Serif_Devanagari({
  subsets: ["devanagari"],
  weight: ["400", "600"],
  variable: "--font-dev-var",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Munshi — ek phone call, poora bharosa",
  description:
    "Munshi is a phone number a parent can call, in their own language, with limits the family sets by voice note.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#c8452b",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body
        className={`${fraunces.variable} ${inter.variable} ${plexMono.variable} ${devanagari.variable}`}
      >
        <SpatialBackgroundMount />
        <TopRail />
        {children}
        <footer className="site-foot">
          <div className="site-foot-inner">
            <p>
              <strong>Munshi</strong> — Scaler × Wispr Flow, &ldquo;India Runs on Voice&rdquo;.
            </p>
            <p className="foot-modes">
              <span className="stamp live">Browser voice: live</span>
              <span className="stamp sandbox">Payments: sandbox (mock)</span>
              <span className="stamp sim">Gas &amp; medicine: simulated</span>
            </p>
            <p className="foot-note">
              No real money moves. Amounts are fetched from the biller, never heard from the caller.
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
