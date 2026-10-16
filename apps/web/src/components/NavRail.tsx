import {
  CalendarDays,
  LayoutGrid,
  LogOut,
  MapPin,
  MessageCircle,
  NotebookTabs,
  Settings,
  Sprout,
} from "lucide-react";

import {
  useAuth,
} from "../providers/AuthProvider";


type Props = {
  onOpenWhatsApp: () => void;
  mobileView: "fields" | "map";
  onMobileViewChange: (view: "fields" | "map") => void;
};

export default function NavRail({ onOpenWhatsApp, mobileView, onMobileViewChange }: Props) {

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


      <button className="rail-button">
        <CalendarDays size={23} />
      </button>


      <button className="rail-button active">
        <LayoutGrid size={23} />
      </button>


      <button className="rail-button">
        <MapPin size={23} />
      </button>


      <button className="rail-button">
        <NotebookTabs size={23} />
      </button>


      <div className="rail-spacer" />


      <button
        type="button"
        className="rail-button whatsapp-rail-button"
        onClick={onOpenWhatsApp}
        title="WhatsApp linking"
        aria-label="Connect WhatsApp account"
      >
        <MessageCircle size={23} /><span className="mobile-nav-label">WhatsApp</span>
      </button>


      <button className="rail-button">
        <Settings size={23} />
      </button>


      <button
        className="rail-button logout-rail-button"

        onClick={() =>
          void logout()
        }

        title="Sign out"
      >
        <LogOut size={23} /><span className="mobile-nav-label">Sign out</span>
      </button>

    </aside>
  );
}
