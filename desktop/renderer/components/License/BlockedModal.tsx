import React, { useState } from "react";
import { useLicenseStore } from "../../stores";

export const BlockedModal: React.FC = () => {
  const {
    isBlocked,
    status,
    usageConsumed,
    usageLimit,
    contactName,
    contactEmail,
    contactPhone,
    supportMessage,
  } = useLicenseStore();

  const [showContactDetails, setShowContactDetails] = useState(false);

  // If not blocked, do not render
  if (!isBlocked && status !== "blocked") {
    return null;
  }

  const handleContactClick = () => {
    if (contactEmail) {
      window.open(`mailto:${contactEmail}?subject=AI%20Teleprompter%20License%20Activation&body=Hello%20${contactName},%20I%20have%20reached%20the%20free%20usage%20limit%20on%20my%20SUT.%20Please%20activate%20or%20upgrade%20my%20license.`);
    }
    setShowContactDetails(true);
  };

  const handleCloseApp = () => {
    if (window.electronAPI?.send) {
      window.electronAPI.send("app:quit");
    } else {
      window.close();
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-md select-none"
      style={{ pointerEvents: "auto" }}
    >
      <div className="relative w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl p-6 text-center space-y-5 animate-in fade-in zoom-in-95 duration-200">
        {/* Top-Right Close Button */}
        <button
          onClick={handleCloseApp}
          className="absolute top-4 right-4 h-7 w-7 rounded-lg bg-slate-800/80 hover:bg-slate-700 active:bg-slate-600 text-slate-400 hover:text-white flex items-center justify-center text-sm transition-colors border border-slate-700/50"
          title="Close Application"
        >
          ✕
        </button>

        {/* Lock Icon */}
        <div className="mx-auto h-12 w-12 rounded-2xl bg-red-950/70 border border-red-500/40 flex items-center justify-center text-xl shadow-lg shadow-red-500/10">
          🔒
        </div>

        {/* Title */}
        <div className="space-y-1.5">
          <h2 className="text-base font-bold tracking-wider text-white uppercase">
            Access Limit Reached
          </h2>
          <p className="text-xs text-slate-300">
            Your free usage allowance has been exhausted.
          </p>
        </div>

        {/* Usage Box */}
        <div className="py-2.5 px-4 bg-slate-950/90 rounded-xl border border-slate-800/80 inline-block">
          <p className="text-[10px] uppercase font-semibold text-slate-500 tracking-wider">
            Usage Allowance
          </p>
          <p className="text-sm font-mono font-bold text-red-400">
            {usageConsumed} / {usageLimit}
          </p>
        </div>

        {/* Contact Message */}
        <div className="space-y-1 text-xs text-slate-300">
          <p>To continue using this application, please contact:</p>
          <p className="text-sm font-bold text-indigo-400 pt-1">
            {contactName || "Diwakar"}
          </p>
          <p className="text-[11px] text-slate-400">
            {supportMessage || "For access activation or license upgrade."}
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-col gap-2.5">
          <button
            onClick={handleContactClick}
            className="w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white font-medium rounded-xl text-xs transition-all shadow-lg shadow-indigo-600/30 flex items-center justify-center gap-2"
          >
            <span>✉️</span>
            <span>Contact {contactName || "Diwakar"}</span>
          </button>

          <button
            onClick={handleCloseApp}
            className="w-full py-2 px-4 bg-slate-800 hover:bg-slate-700 active:bg-slate-600 text-slate-300 hover:text-white font-medium rounded-xl text-xs transition-colors border border-slate-700/60 flex items-center justify-center gap-2"
          >
            <span>✕</span>
            <span>Close Application</span>
          </button>
        </div>

        {/* Details Dropdown */}
        {showContactDetails && (
          <div className="p-3 bg-slate-950 rounded-xl border border-slate-800 text-[11px] text-left space-y-1 text-slate-300 animate-in fade-in duration-150">
            <p className="font-semibold text-slate-200">Support Coordinates:</p>
            {contactEmail && <p>• Email: <span className="font-mono text-cyan-400">{contactEmail}</span></p>}
            {contactPhone && <p>• Phone: <span className="font-mono text-slate-300">{contactPhone}</span></p>}
            <p className="text-[10px] text-slate-500 pt-1">The administrator will remotely unblock or allocate usage once verified.</p>
          </div>
        )}
      </div>
    </div>
  );
};
