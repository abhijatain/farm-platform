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


type Props = { onOpenWhatsApp: () => void };

export default function NavRail({ onOpenWhatsApp }: Props) {

  const {
    logout,
  } =
    useAuth();


  return (
    <aside className="nav-rail">

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
        className="rail-button"
        onClick={onOpenWhatsApp}
        title="WhatsApp linking"
        aria-label="Connect WhatsApp account"
      >
        <MessageCircle size={23} />
      </button>


      <button className="rail-button">
        <Settings size={23} />
      </button>


      <button
        className="rail-button"

        onClick={() =>
          void logout()
        }

        title="Sign out"
      >
        <LogOut size={23} />
      </button>

    </aside>
  );
}
