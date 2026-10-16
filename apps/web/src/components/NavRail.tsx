import {
  LayoutGrid,
  LogOut,
  MapPin,
  MessageCircle,
  Sprout,
} from "lucide-react";

import { whatsappEnabled } from "../lib/featureFlags";

import {
  useAuth,
} from "../providers/AuthProvider";


type Props = {
  onOpenWhatsApp: () => void;
  mobileView: "fields" | "map";
  onMobileViewChange: (view: "fields" | "map") => void;
  sidebarExpanded: boolean;
  onSidebarExpandedChange: (expanded: boolean) => void;
};

export default function NavRail({ onOpenWhatsApp, mobileView, onMobileViewChange, sidebarExpanded, onSidebarExpandedChange }: Props) {

  const {
    logout,
  } =
    useAuth();


  return (
    <aside className="nav-rail" aria-label="Main navigation">
      <button type="button" className={"mobile-rail-button" + (mobileView === "fields" ? " active" : "")}
        onClick={() => onMobileViewChange("fields")} aria-label="Show fields" aria-current={mobileView === "fields" ? "page" : undefined}>
        <LayoutGrid size={22} /><span>Fields</span>
      </button>
      <button type="button" className={"mobile-rail-button" + (mobileView === "map" ? " active" : "")}
        onClick={() => onMobileViewChange("map")} aria-label="Show map" aria-current={mobileView === "map" ? "page" : undefined}>
        <MapPin size={22} /><span>Map</span>
      </button>

      <div className="brand-button">
        <Sprout size={26} />
      </div>


      <button type="button"
        className={"rail-button desktop-rail-button" + (sidebarExpanded ? " active" : "")}
        onClick={() => { onSidebarExpandedChange(true); onMobileViewChange("fields"); }}
        title="Show field list" aria-label="Show field list" aria-pressed={sidebarExpanded}>
        <LayoutGrid size={23} />
      </button>
      <button type="button"
        className={"rail-button desktop-rail-button" + (!sidebarExpanded ? " active" : "")}
        onClick={() => { onSidebarExpandedChange(false); onMobileViewChange("map"); }}
        title="Expand map and hide field list" aria-label="Expand map and hide field list"
        aria-pressed={!sidebarExpanded}>
        <MapPin size={23} />
      </button>

      <div className="rail-account-actions" aria-label="Account actions">
        {whatsappEnabled && (
          <button
            type="button"
            className="rail-button whatsapp-rail-button"
            onClick={onOpenWhatsApp}
            title="WhatsApp linking"
            aria-label="Connect WhatsApp account"
          >
            <MessageCircle size={22} />
            <span className="mobile-nav-label">WhatsApp</span>
            <span className="desktop-nav-label">WhatsApp</span>
          </button>
        )}
        <button
          type="button"
          className="rail-button logout-rail-button"
          onClick={() => void logout()}
          title="Sign out"
          aria-label="Sign out"
        >
          <LogOut size={22} />
          <span className="mobile-nav-label">Sign out</span>
          <span className="desktop-nav-label">Sign out</span>
        </button>
      </div>

    </aside>
  );
}
