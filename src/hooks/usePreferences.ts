import { useCallback, useEffect, useState } from 'react';

export type Theme = 'aurora' | 'ember' | 'glacier' | 'jade';
export type TextSize = 'normal' | 'large';

export interface Preferences {
  theme: Theme;
  textSize: TextSize;
  motion: boolean;
  video: boolean;
}

const STORAGE_KEY = 'asme:preferences';

const prefersReducedMotion = () =>
  typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

export const DEFAULT_PREFERENCES: Preferences = {
  theme: 'aurora',
  textSize: 'normal',
  motion: true,
  video: true,
};

function load(): Preferences {
  const base = { ...DEFAULT_PREFERENCES, motion: !prefersReducedMotion() };
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? { ...base, ...(JSON.parse(raw) as Partial<Preferences>) } : base;
  } catch {
    return base;
  }
}

export function usePreferences() {
  const [prefs, setPrefs] = useState<Preferences>(load);

  // Reflect preferences on <html> so plain CSS can react to them.
  useEffect(() => {
    const root = document.documentElement;
    root.dataset.theme = prefs.theme;
    root.dataset.text = prefs.textSize;
    root.dataset.motion = prefs.motion ? 'on' : 'off';
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
    } catch {
      /* storage unavailable — preferences just won't persist */
    }
  }, [prefs]);

  const update = useCallback(<K extends keyof Preferences>(key: K, value: Preferences[K]) => {
    setPrefs((p) => ({ ...p, [key]: value }));
  }, []);

  const reset = useCallback(() => setPrefs({ ...DEFAULT_PREFERENCES, motion: !prefersReducedMotion() }), []);

  return { prefs, update, reset };
}
