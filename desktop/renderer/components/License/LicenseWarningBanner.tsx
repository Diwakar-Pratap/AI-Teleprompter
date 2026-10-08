import React, { useState } from "react";
import { useLicenseStore } from "../../stores";

export const LicenseWarningBanner: React.FC = () => {
  const { warningLevel, usageConsumed, usageLimit, contactName } = useLicenseStore();
  const [dismissed, setDismissed] = useState(false);

  // If no warning or limit is reached (limit_reached is handled by BlockedModal) or dismissed
  if (!warningLevel || warningLevel === "limit_reached" || dismissed) {
    return null;
  }

  const is90 = warningLevel === "warning_90";

  return (
    <div
      className={`px-3 py-1.5 text-xs flex items-center justify-between border-b transition-all ${
        is90
          ? "bg-amber-950/80 border-amber-500/40 text-amber-200"
          : "bg-yellow-950/70 border-yellow-500/30 text-yellow-200"
      }`}
    >
      <div className="flex items-center gap-2 truncate">
        <span>⚠️</span>
        <span className="truncate">
          {is90
            ? `Warning: 90% of free usage used (${usageConsumed}/${usageLimit}). Contact ${contactName || "Diwakar"} to upgrade.`
            : `Notice: 80% of free usage used (${usageConsumed}/${usageLimit}).`}
        </span>
      </div>
      <button
        onClick={() => setDismissed(true)}
        className="ml-2 text-xs opacity-60 hover:opacity-100 p-0.5"
        title="Dismiss notice"
      >
        ✕
      </button>
    </div>
  );
};
