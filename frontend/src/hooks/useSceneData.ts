import { useEffect } from "react";
import { useSimulationStore } from "../store/simulationStore";
import type { ScenePayload } from "../types";

/** Fetches the Python-exported scene.json once on mount. */
export function useSceneData(): void {
  const setData = useSimulationStore((s) => s.setData);
  const setLoadError = useSimulationStore((s) => s.setLoadError);

  useEffect(() => {
    let cancelled = false;

    fetch("/data/scene.json")
      .then((res) => {
        if (!res.ok) {
          throw new Error(
            `HTTP ${res.status} fetching scene.json — run "uv run python main.py" ` +
              "from the repo root to (re)generate frontend/public/data/scene.json."
          );
        }
        return res.json() as Promise<ScenePayload>;
      })
      .then((payload) => {
        if (!cancelled) setData(payload);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setLoadError(err instanceof Error ? err.message : String(err));
        }
      });

    return () => {
      cancelled = true;
    };
  }, [setData, setLoadError]);
}
