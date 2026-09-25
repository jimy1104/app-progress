import { useEffect, useRef, useState } from 'react';
import { Contrast, Film, Palette, RotateCcw, SlidersHorizontal, Type, Wand2, X } from 'lucide-react';
import type { Preferences, Theme } from '../hooks/usePreferences';

const THEMES: { id: Theme; name: string; colors: [string, string, string] }[] = [
  { id: 'aurora', name: 'Aurora', colors: ['#5eead4', '#a78bfa', '#fbbf24'] },
  { id: 'ember', name: 'Ember', colors: ['#fb923c', '#f472b6', '#facc15'] },
  { id: 'glacier', name: 'Glacier', colors: ['#7dd3fc', '#818cf8', '#e0f2fe'] },
  { id: 'jade', name: 'Jade', colors: ['#34d399', '#a3e635', '#2dd4bf'] },
];

interface Props {
  prefs: Preferences;
  update: <K extends keyof Preferences>(key: K, value: Preferences[K]) => void;
  reset: () => void;
}

function Switch({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={`relative h-7 w-12 shrink-0 rounded-full transition-colors duration-300 ${
        checked ? 'bg-[rgb(var(--a1))]' : 'bg-white/15'
      }`}
    >
      <span
        className={`absolute left-1 top-1 h-5 w-5 rounded-full bg-white shadow transition-transform duration-300 ${
          checked ? 'translate-x-5' : ''
        }`}
      />
    </button>
  );
}

function Row({ icon: Icon, title, hint, children }: { icon: typeof Film; title: string; hint: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-2xl bg-white/[0.04] px-4 py-3">
      <div className="flex items-center gap-3 text-left">
        <Icon size={18} className="shrink-0 text-[rgb(var(--a1))]" />
        <div>
          <p className="text-sm font-semibold text-white">{title}</p>
          <p className="text-xs text-white/50">{hint}</p>
        </div>
      </div>
      {children}
    </div>
  );
}

export default function Personalize({ prefs, update, reset }: Props) {
  const [open, setOpen] = useState(false);
  const [hinted, setHinted] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const toggleRef = useRef<HTMLButtonElement>(null);

  // Draw attention to the button once, shortly after the intro.
  useEffect(() => {
    const t = window.setTimeout(() => setHinted(true), 9000);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      setOpen(false);
      toggleRef.current?.focus();
    };
    const onClick = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener('keydown', onKey);
    window.addEventListener('mousedown', onClick);
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('mousedown', onClick);
    };
  }, [open]);

  return (
    <div ref={rootRef} className="fixed bottom-5 right-5 z-30 flex flex-col items-end gap-3">
      {open && (
        <div
          role="dialog"
          aria-label="Personalize"
          className="glass-panel liquid-glass sheet-in max-h-[calc(100dvh-6.5rem)] w-[min(22rem,calc(100vw-2.5rem))] overflow-y-auto rounded-3xl p-4 shadow-2xl"
        >
          <div className="mb-3 flex items-center justify-between px-1">
            <div className="flex items-center gap-2">
              <Wand2 size={16} className="text-[rgb(var(--a3))]" />
              <p className="text-sm font-semibold text-white">Make it yours</p>
            </div>
            <button
              onClick={reset}
              className="flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium text-white/60 transition-colors hover:bg-white/10 hover:text-white"
            >
              <RotateCcw size={12} /> Reset
            </button>
          </div>

          <div className="space-y-2">
            <div className="rounded-2xl bg-white/[0.04] p-4">
              <div className="mb-3 flex items-center gap-3">
                <Palette size={18} className="text-[rgb(var(--a1))]" />
                <p className="text-sm font-semibold text-white">Color mood</p>
              </div>
              <div className="grid grid-cols-4 gap-2">
                {THEMES.map((t) => {
                  const active = prefs.theme === t.id;
                  return (
                    <button
                      key={t.id}
                      onClick={() => update('theme', t.id)}
                      aria-pressed={active}
                      className={`group flex flex-col items-center gap-1.5 rounded-xl py-2 transition-colors ${
                        active ? 'bg-white/10' : 'hover:bg-white/5'
                      }`}
                    >
                      <span
                        className={`h-9 w-9 rounded-full ring-2 ring-offset-2 ring-offset-[#0b0c12] transition-transform duration-300 group-hover:scale-110 ${
                          active ? 'ring-white' : 'ring-transparent'
                        }`}
                        style={{ background: `conic-gradient(${t.colors[0]}, ${t.colors[1]}, ${t.colors[2]}, ${t.colors[0]})` }}
                      />
                      <span className={`text-[11px] font-medium ${active ? 'text-white' : 'text-white/60'}`}>{t.name}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            <Row icon={Type} title="Text size" hint="Easier reading">
              <div className="flex rounded-full bg-white/10 p-1" role="radiogroup" aria-label="Text size">
                {(['normal', 'large'] as const).map((size) => (
                  <button
                    key={size}
                    role="radio"
                    aria-checked={prefs.textSize === size}
                    onClick={() => update('textSize', size)}
                    className={`rounded-full px-3 py-1 font-semibold transition-colors ${
                      size === 'large' ? 'text-base' : 'text-xs'
                    } ${prefs.textSize === size ? 'bg-white text-black' : 'text-white/70 hover:text-white'}`}
                  >
                    A
                  </button>
                ))}
              </div>
            </Row>

            <Row icon={SlidersHorizontal} title="Animations" hint="Movement & effects">
              <Switch label="Animations" checked={prefs.motion} onChange={(v) => update('motion', v)} />
            </Row>

            <Row icon={Contrast} title="High contrast" hint="Clearer text over video">
              <Switch label="High contrast" checked={prefs.contrast} onChange={(v) => update('contrast', v)} />
            </Row>

            <Row icon={Film} title="Background video" hint="Play the scenery">
              <Switch label="Background video" checked={prefs.video} onChange={(v) => update('video', v)} />
            </Row>
          </div>
        </div>
      )}

      <button
        ref={toggleRef}
        onClick={() => {
          setOpen((o) => !o);
          setHinted(false);
        }}
        aria-expanded={open}
        aria-label={open ? 'Close personalization' : 'Personalize'}
        className={`reveal liquid-glass glass-panel group flex items-center gap-2 rounded-full p-2.5 text-sm sm:py-3 sm:pl-3.5 sm:pr-5 font-medium text-white shadow-xl transition-transform hover:scale-[1.03] ${
          hinted && !open ? 'pulse-ring' : ''
        }`}
        style={{ ['--d' as string]: '1700ms' }}
      >
        <span className="accent-dot grid h-8 w-8 place-items-center rounded-full text-black sm:h-7 sm:w-7 transition-transform duration-500 group-hover:rotate-180">
          {open ? <X size={15} /> : <Palette size={15} />}
        </span>
        <span className="hidden sm:inline">{open ? 'Close' : 'Personalize'}</span>
      </button>
    </div>
  );
}
