import { useCallback, useEffect, useState } from "react";
import { CheckCircle, WarningCircle } from "@phosphor-icons/react";
import { api, setApiKey } from "./api.js";
import TopBar from "./components/TopBar.jsx";
import ApplicationsView from "./components/ApplicationsView.jsx";
import AnalyticsView from "./components/AnalyticsView.jsx";
import MatchesView from "./components/MatchesView.jsx";

const ROUTES = { "#/analytics": "analytics", "#/matches": "matches" };

function KeyGate({ onSubmit }) {
  const [value, setValue] = useState("");
  return (
    <form
      className="key-gate"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(value.trim());
      }}
    >
      <h1>Enter access key</h1>
      <input
        type="password"
        autoFocus
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="API key"
      />
      <button type="submit">Continue</button>
    </form>
  );
}

function useHashRoute() {
  const read = () => ROUTES[window.location.hash] ?? "applications";
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
  const [needsKey, setNeedsKey] = useState(false);

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
      if (err.status === 401) {
        setNeedsKey(true);
      } else {
        setLoadError(err.message);
      }
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  if (needsKey) {
    return (
      <KeyGate
        onSubmit={(key) => {
          setApiKey(key);
          setNeedsKey(false);
          reload();
        }}
      />
    );
  }

  return (
    <>
      <TopBar route={route} />
      {route === "applications" && (
        <ApplicationsView
          apps={apps}
          loadError={loadError}
          reload={reload}
          notify={notify}
        />
      )}
      {route === "analytics" && <AnalyticsView apps={apps} />}
      {route === "matches" && <MatchesView notify={notify} />}
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
