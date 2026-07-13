import { useCallback, useEffect, useState } from "react";
import { CheckCircle, WarningCircle } from "@phosphor-icons/react";
import { api } from "./api.js";
import TopBar from "./components/TopBar.jsx";
import ApplicationsView from "./components/ApplicationsView.jsx";
import AnalyticsView from "./components/AnalyticsView.jsx";

function useHashRoute() {
  const read = () =>
    window.location.hash === "#/analytics" ? "analytics" : "applications";
  const [route, setRoute] = useState(read);
  useEffect(() => {
    const onChange = () => setRoute(read());
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}

export default function App() {
  const route = useHashRoute();
  const [apps, setApps] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [toast, setToast] = useState(null);

  const notify = useCallback((message, kind = "ok") => {
    setToast({ message, kind });
  }, []);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(t);
  }, [toast]);

  const reload = useCallback(async () => {
    try {
      setLoadError(null);
      setApps(await api.listApplications());
    } catch (err) {
      setLoadError(err.message);
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  return (
    <>
      <TopBar route={route} />
      {route === "applications" ? (
        <ApplicationsView
          apps={apps}
          loadError={loadError}
          reload={reload}
          notify={notify}
        />
      ) : (
        <AnalyticsView apps={apps} />
      )}
      {toast && (
        <div className={`toast ${toast.kind === "error" ? "error" : ""}`} role="status">
          {toast.kind === "error" ? (
            <WarningCircle size={17} weight="bold" aria-hidden />
          ) : (
            <CheckCircle size={17} weight="bold" aria-hidden />
          )}
          {toast.message}
        </div>
      )}
    </>
  );
}
