"use client";

interface CardLogoProps {
    type: string;
    className?: string;
}

export default function CardLogo({ type, className = "" }: CardLogoProps) {
    const cardStyles = {
        visa: {
            gradient: "from-blue-600 to-blue-400",
            text: "VISA",
        },
        mastercard: {
            gradient: "from-red-600 to-orange-500",
            text: "MC",
        },
        amex: {
            gradient: "from-blue-500 to-blue-300",
            text: "AMEX",
        },
        discover: {
            gradient: "from-orange-600 to-orange-400",
            text: "DISC",
        },
        unknown: {
            gradient: "from-gray-600 to-gray-400",
            text: "CARD",
        },
    };

    const style = cardStyles[type as keyof typeof cardStyles] || cardStyles.unknown;

    return (
        <div
            className={`h-10 w-16 rounded bg-gradient-to-r ${style.gradient} flex items-center justify-center text-white text-xs font-bold shadow-md ${className}`}
        >
            {style.text}
        </div>
    );
}
