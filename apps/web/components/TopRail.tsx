"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { RotateCcw, PhoneCall, BookOpen, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";

const links = [
  { href: "/", label: "Call Stage", icon: PhoneCall },
  { href: "/console", label: "Family Console", icon: BookOpen },
  { href: "/trace", label: "Under the Hood", icon: ShieldCheck },
];

export default function TopRail() {
  const pathname = usePathname();
  const router = useRouter();
  const [resetting, setResetting] = useState(false);
  const [resetLabel, setResetLabel] = useState<string | null>(null);

  const handleReset = async () => {
    setResetting(true);
    setResetLabel(null);
    try {
      const res = await api.resetDemo();
      setResetLabel(`Reset ${Math.round(res.reset_ms)}ms`);
      window.dispatchEvent(new CustomEvent("munshi:demo-reset"));
      router.refresh();
      setTimeout(() => setResetLabel(null), 2500);
    } catch {
      setResetLabel("API offline");
      setTimeout(() => setResetLabel(null), 2500);
    } finally {
      setResetting(false);
    }
  };

  return (
    <header className="rail">
      <Link className="brand" href="/" aria-label="Munshi home">
        <span className="brand-hindi" aria-hidden="true">
          मुंशी
        </span>
        <span className="brand-latin">
          <span>MUNSHI</span>
          <small>ghar se door, kaam paas</small>
        </span>
      </Link>
      <nav className="rail-nav" aria-label="Sections">
        {links.map((link) => {
          const Icon = link.icon;
          return (
            <Link
              key={link.href}
              href={link.href}
              aria-current={pathname === link.href ? "page" : undefined}
            >
              <Icon size={14} strokeWidth={1.8} aria-hidden="true" />
              <span>{link.label}</span>
            </Link>
          );
        })}
      </nav>
      <div className="rail-meta">
        <span className="stamp sandbox">Demo · sandbox</span>
        <button
          type="button"
          className="btn btn-sm rail-reset"
          onClick={() => void handleReset()}
          disabled={resetting}
          title="Restore synthetic Devi family and clean ledger"
        >
          <RotateCcw size={13} strokeWidth={1.8} aria-hidden="true" />
          <span>{resetLabel ?? (resetting ? "Resetting…" : "Reset demo")}</span>
        </button>
      </div>
    </header>
  );
}
