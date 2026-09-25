import { FormEvent, useEffect, useRef, useState } from 'react';
import { ArrowRight, Check, Loader2, Mail, Sparkles } from 'lucide-react';
import Magnetic from './Magnetic';

type Status = 'idle' | 'loading' | 'success' | 'error';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** Fired by "Sign Up" buttons elsewhere on the page. */
export const FOCUS_EMAIL_EVENT = 'asme:focus-email';

const motionAllowed = () =>
  document.documentElement.dataset.motion !== 'off' &&
  !window.matchMedia('(prefers-reduced-motion: reduce)').matches;

const SHAKE: Keyframe[] = [
  { transform: 'translateX(0)' },
  { transform: 'translateX(-7px)' },
  { transform: 'translateX(6px)' },
  { transform: 'translateX(-4px)' },
  { transform: 'translateX(3px)' },
  { transform: 'translateX(0)' },
];
const ATTENTION: Keyframe[] = [
  { transform: 'scale(1)' },
  { transform: 'scale(1.035)' },
  { transform: 'scale(0.99)' },
  { transform: 'scale(1)' },
];
const SPARKS = Array.from({ length: 12 }, (_, i) => {
  const angle = (i / 12) * Math.PI * 2;
  const dist = 38 + (i % 3) * 14;
  return { x: Math.cos(angle) * dist, y: Math.sin(angle) * dist, color: `var(--a${(i % 3) + 1})` };
});

/** Splits a phrase into individually animated letters. */
function Letters({ text, offset = 0 }: { text: string; offset?: number }) {
  return (
    <>
      {[...text].map((ch, i) =>
        ch === ' ' ? (
          <span key={i}> </span>
        ) : (
          <span key={i} className="letter" style={{ ['--d' as string]: `${offset + i * 45}ms` }}>
            {ch}
          </span>
        ),
      )}
    </>
  );
}

export default function Hero() {
  const [email, setEmail] = useState('');
  const [status, setStatus] = useState<Status>('idle');
  const [focused, setFocused] = useState(false);
  const timer = useRef<number | null>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const play = (frames: Keyframe[], duration: number) => {
    if (motionAllowed()) formRef.current?.animate(frames, { duration, easing: 'cubic-bezier(.36,.07,.19,.97)' });
  };

  useEffect(() => () => void (timer.current !== null && clearTimeout(timer.current)), []);

  // "Sign Up" anywhere on the page brings the visitor straight here.
  useEffect(() => {
    const onFocusEmail = () => {
      inputRef.current?.focus();
      play(ATTENTION, 600);
    };
    window.addEventListener(FOCUS_EMAIL_EVENT, onFocusEmail);
    return () => window.removeEventListener(FOCUS_EMAIL_EVENT, onFocusEmail);
  }, []);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (status === 'loading') return;
    if (!EMAIL_RE.test(email.trim())) {
      setStatus('error');
      play(SHAKE, 450);
      inputRef.current?.focus();
      return;
    }
    setStatus('loading');
    timer.current = window.setTimeout(() => {
      setStatus('success');
      timer.current = window.setTimeout(() => {
        setStatus('idle');
        setEmail('');
      }, 4200);
    }, 1100);
  };

  const done = status === 'success';

  return (
    <section className="relative z-10 flex flex-1 -translate-y-[20%] flex-col items-center justify-center px-6 py-12 text-center">
      <h1
        className="mb-8 whitespace-nowrap text-[min(2.6rem,10.5vw)] leading-none tracking-tight text-white sm:text-5xl md:text-6xl lg:text-7xl"
        style={{ fontFamily: "'Instrument Serif', serif" }}
      >
        <Letters text="Built for the " offset={150} />
        <span className="relative inline-block italic">
          <span className="letter" style={{ ['--d' as string]: `${150 + 14 * 45}ms` }}>
            <span className="text-accent-gradient pr-[0.08em]">curious</span>
          </span>
          <svg
            aria-hidden="true"
            className="swoosh absolute -bottom-[0.18em] left-0 h-[0.3em] w-full overflow-visible"
            viewBox="0 0 200 20"
            preserveAspectRatio="none"
          >
            <path
              d="M3 14 C 50 4, 120 2, 197 9"
              pathLength={1}
              fill="none"
              stroke="url(#swoosh)"
              strokeWidth="3"
              strokeLinecap="round"
            />
            <defs>
              <linearGradient id="swoosh" x1="0" x2="1">
                <stop offset="0" stopColor="rgb(var(--a1))" />
                <stop offset="0.5" stopColor="rgb(var(--a2))" />
                <stop offset="1" stopColor="rgb(var(--a3))" />
              </linearGradient>
            </defs>
          </svg>
        </span>
      </h1>

      <div className="w-full max-w-xl space-y-4">
        <div className="reveal relative" style={{ ['--d' as string]: '900ms' }}>
          {/* soft accent halo behind the input */}
          <div
            aria-hidden="true"
            className={`absolute -inset-3 rounded-full bg-[linear-gradient(90deg,rgb(var(--a1)/0.35),rgb(var(--a2)/0.3),rgb(var(--a3)/0.3))] blur-2xl transition-opacity duration-500 ${
              done ? 'opacity-90' : focused ? 'opacity-60' : 'opacity-0'
            }`}
          />
          <form
            ref={formRef}
            noValidate
            onSubmit={onSubmit}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            className={`group liquid-glass flex items-center gap-3 rounded-full py-2 pl-6 pr-2 transition-shadow duration-300 focus-within:shadow-[0_0_0_1px_rgb(var(--a1)/0.5),0_10px_40px_-10px_rgb(var(--a1)/0.5)] ${
              status === 'error' ? 'shadow-[0_0_0_1px_rgb(251_113_133/0.7)]' : ''
            }`}
          >
            {/* periodic light sweep that guides the eye to the main action */}
            {!focused && !done && (
              <span aria-hidden="true" className="sheen pointer-events-none absolute inset-y-0 left-0 w-1/3" />
            )}
            {done ? (
              <p className="pop flex-1 text-left text-sm text-white sm:text-base" role="status">
                You&rsquo;re on the list — welcome aboard.
              </p>
            ) : (
              <>
                <Mail size={18} className="shrink-0 text-white/40 transition-colors group-focus-within:text-[rgb(var(--a1))]" />
                <input
                  ref={inputRef}
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    if (status === 'error') setStatus('idle');
                  }}
                  placeholder="Enter your email"
                  aria-label="Email address"
                  aria-invalid={status === 'error'}
                  aria-describedby="email-hint"
                  autoComplete="email"
                  disabled={status === 'loading'}
                  className="min-w-0 flex-1 bg-transparent text-base text-white outline-none placeholder:text-white/40"
                />
              </>
            )}
            <Magnetic strength={0.3}>
            <button
              type="submit"
              aria-label="Subscribe"
              disabled={status === 'loading' || done}
              className={`relative shrink-0 rounded-full p-3 text-black transition-all duration-300 hover:scale-105 active:scale-95 disabled:hover:scale-100 ${
                done ? 'bg-[rgb(var(--a1))]' : 'bg-white hover:shadow-[0_0_24px_rgb(var(--a1)/0.6)]'
              }`}
            >
              {status === 'loading' ? (
                <Loader2 size={20} className="animate-spin" />
              ) : done ? (
                <Check size={20} className="pop" />
              ) : (
                <ArrowRight size={20} className="transition-transform duration-300 group-hover:translate-x-0.5" />
              )}
            </button>
            </Magnetic>
          </form>

          {/* celebratory burst on success */}
          {done && (
            <span aria-hidden="true" className="pointer-events-none absolute right-7 top-1/2">
              {SPARKS.map((s, i) => (
                <span
                  key={i}
                  className="spark"
                  style={{
                    background: `rgb(${s.color})`,
                    ['--x' as string]: `${s.x}px`,
                    ['--y' as string]: `${s.y}px`,
                  }}
                />
              ))}
            </span>
          )}

          <p
            id="email-hint"
            aria-live="polite"
            className={`absolute left-6 top-full mt-1.5 text-xs font-medium text-rose-300 transition-all duration-300 ${
              status === 'error' ? 'translate-y-0 opacity-100' : '-translate-y-1 opacity-0'
            }`}
          >
            {status === 'error' ? 'Please enter a valid email address.' : ''}
          </p>
        </div>

        <p className="reveal px-4 pt-3 text-sm leading-relaxed text-white" style={{ ['--d' as string]: '1050ms' }}>
          Stay updated with the latest news and insights. Subscribe to our newsletter today and never miss out on
          exciting updates.
        </p>

        <div className="reveal flex justify-center" style={{ ['--d' as string]: '1200ms' }}>
          <Magnetic strength={0.15}>
          <button className="group liquid-glass inline-flex items-center gap-2 rounded-full px-8 py-3 text-sm font-medium text-white transition-colors hover:bg-white/5">
            <Sparkles
              size={16}
              className="text-[rgb(var(--a3))] transition-transform duration-500 group-hover:rotate-[20deg] group-hover:scale-125"
            />
            Manifesto
          </button>
          </Magnetic>
        </div>
      </div>
    </section>
  );
}
