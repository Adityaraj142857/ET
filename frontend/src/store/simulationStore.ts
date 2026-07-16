import { create } from "zustand";
import type { ScenePayload } from "../types";

interface SimulationState {
  data: ScenePayload | null;
  loading: boolean;
  error: string | null;

  currentStep: number;
  playing: boolean;
  speedStepsPerTick: number; // how many 5-min steps advance per playback tick

  selectedOvenId: string | null;

  setData: (data: ScenePayload) => void;
  setLoadError: (message: string) => void;

  setStep: (step: number) => void;
  advanceStep: () => void;
  togglePlaying: () => void;
  setPlaying: (playing: boolean) => void;
  setSpeed: (stepsPerTick: number) => void;

  selectOven: (ovenId: string | null) => void;
}

export const useSimulationStore = create<SimulationState>((set, get) => ({
  data: null,
  loading: true,
  error: null,

  currentStep: 0,
  playing: false,
  speedStepsPerTick: 4, // matches the default-highlighted "4x" button in TimeScrubber

  selectedOvenId: null,

  setData: (data) => set({ data, loading: false, error: null }),
  setLoadError: (message) => set({ error: message, loading: false }),

  setStep: (step) => {
    const n = get().data?.meta.n_steps ?? 1;
    const clamped = Math.max(0, Math.min(n - 1, step));
    set({ currentStep: clamped });
  },
  advanceStep: () => {
    const { data, currentStep, speedStepsPerTick } = get();
    if (!data) return;
    const n = data.meta.n_steps;
    const next = currentStep + speedStepsPerTick;
    if (next >= n - 1) {
      set({ currentStep: n - 1, playing: false });
    } else {
      set({ currentStep: next });
    }
  },
  togglePlaying: () => set((s) => ({ playing: !s.playing })),
  setPlaying: (playing) => set({ playing }),
  setSpeed: (speedStepsPerTick) => set({ speedStepsPerTick }),

  selectOven: (ovenId) => set({ selectedOvenId: ovenId }),
}));
