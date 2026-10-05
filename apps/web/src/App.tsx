import {
  AuthProvider,
  useAuth,
} from "./providers/AuthProvider";

import LoginPage
  from "./components/LoginPage";

import FarmWorkspace
  from "./components/FarmWorkspace";


function Application() {
  const {
    user,
    loading,
  } = useAuth();


  if (loading) {
    return (
      <div className="app-loading">
        Loading…
      </div>
    );
  }


  if (!user) {
    return <LoginPage />;
  }


  return <FarmWorkspace />;
}


export default function App() {
  return (
    <AuthProvider>
      <Application />
    </AuthProvider>
  );
}
