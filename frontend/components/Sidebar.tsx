"use client";

import { MessageSquare, BarChart3, Monitor, FileText, Wallet, MapPin, Settings } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import Image from "next/image";

const navItems = [
    { name: "Chat", href: "/", icon: MessageSquare },
    { name: "Workflow", href: "/workflow", icon: BarChart3 },
    { name: "Live Browser", href: "/live-browser", icon: Monitor },
    { name: "Data Review", href: "/data-review", icon: FileText },
    { name: "Wallet", href: "/wallet", icon: Wallet },
    { name: "Addresses", href: "/addresses", icon: MapPin },
    { name: "Settings", href: "/settings", icon: Settings },
];

export default function Sidebar() {
    const pathname = usePathname();

    return (
        <div className="w-64 h-screen border-r border-primary/30 flex flex-col" style={{background: '#0a1929'}}>
            {/* Logo - Using uploaded image */}
            <div className="p-6 border-b border-primary/30">
                <div className="flex flex-col items-center gap-3">
                    {/* Your uploaded logo - BIGGER */}
                    <Image
                        src="/cartmind-logo.png?v=2"
                        alt="CARTMIND-AI Logo"
                        width={120}
                        height={80}
                        className="object-contain"
                        priority
                        unoptimized
                    />

                    {/* Brand Name */}
                    <div className="text-center">
                        <h1 className="text-xl font-bold">
                            <span className="text-white">CART</span>
                            <span className="gradient-text">MIND-AI</span>
                        </h1>
                        <p className="text-xs text-text-secondary mt-0.5">Smart Checkout</p>
                    </div>
                </div>
            </div>

            {/* Navigation */}
            <nav className="flex-1 p-4 space-y-2">
                {navItems.map((item) => {
                    const Icon = item.icon;
                    const isActive = pathname === item.href;

                    return (
                        <Link
                            key={item.name}
                            href={item.href}
                            style={isActive ? {
                                background: '#3b82f6',
                                boxShadow: '0 0 50px rgba(59, 130, 246, 1), 0 0 30px rgba(59, 130, 246, 0.8), inset 0 0 20px rgba(59, 130, 246, 0.4)'
                            } : {}}
                            className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-all ${isActive
                                    ? "text-white border-2 border-primary scale-105 font-semibold"
                                    : "glass text-text-secondary hover:text-text-primary hover:shadow-lg hover:scale-105"
                                }`}
                        >
                            <Icon size={20} />
                            <span className="font-medium">{item.name}</span>
                        </Link>
                    );
                })}
            </nav>

            {/* Footer */}
            <div className="p-4 border-t border-primary/30">
                <div className="text-xs text-text-secondary text-center">
                    v1.0.0
                </div>
            </div>
        </div>
    );
}
