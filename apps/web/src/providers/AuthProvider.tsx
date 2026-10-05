import {
  createContext,
  type ReactNode,
  useContext,
  useEffect,
  useState,
} from "react";

import {
  onAuthStateChanged,
  signOut,
  type User,
} from "firebase/auth";

import {
  auth,
} from "../lib/firebase";

import {
  getMe,
} from "../lib/api";

import type {
  CurrentUser,
} from "../types/api";


type AuthContextValue = {

  user:
    User | null;

  profile:
    CurrentUser | null;

  loading:
    boolean;

  logout:
    () => Promise<void>;

};


const AuthContext =
  createContext<
    AuthContextValue | null
  >(null);


export function AuthProvider({
  children,
}: {
  children:
    ReactNode;
}) {

  const [
    user,
    setUser,
  ] =
    useState<
      User | null
    >(null);


  const [
    profile,
    setProfile,
  ] =
    useState<
      CurrentUser | null
    >(null);


  const [
    loading,
    setLoading,
  ] =
    useState(true);


  useEffect(() => {

    return onAuthStateChanged(
      auth,

      async (
        firebaseUser,
      ) => {

        setUser(
          firebaseUser,
        );


        if (
          !firebaseUser
        ) {

          setProfile(null);

          setLoading(false);

          return;

        }


        try {

          /*
           * This also causes our
           * FastAPI backend to create
           * the PostgreSQL user on
           * first login.
           */

          const me =
            await getMe();


          setProfile(me);

        } catch (
          error
        ) {

          console.error(
            "Backend auth sync failed:",
            error,
          );

        } finally {

          setLoading(false);

        }

      },
    );

  }, []);


  async function logout() {

    await signOut(
      auth,
    );

  }


  return (
    <AuthContext.Provider
      value={{
        user,
        profile,
        loading,
        logout,
      }}
    >

      {children}

    </AuthContext.Provider>
  );
}


export function useAuth() {

  const context =
    useContext(
      AuthContext,
    );


  if (!context) {

    throw new Error(
      "useAuth must be used inside AuthProvider.",
    );

  }


  return context;
}
