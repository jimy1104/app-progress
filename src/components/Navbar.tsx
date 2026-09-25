import { useEffect, useRef, useState } from 'react';
import { Globe, Menu, X } from 'lucide-react';

const LINKS = ['Features', 'Pricing', 'About'];

export default function Navbar() {
  const [pill, setPill] = useState<{ left: number; width: number } | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Sliding highlight that follows the hovered / focused link.
  const track = (el: HTMLElement) => setPill({ left: el.offsetLeft, width: el.offsetWidth });

  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setMenuOpen(false);
    const onClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    };
    window.addEventListener('keydown', onKey);
    window.addEventListener('mousedown', onClick);
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('mousedown', onClick);
    };
  }, [menuOpen]);

  return (
    <nav className="reveal relative z-20 py-6 pl-6 pr-6" style={{ ['--d' as string]: '650ms' }}>
      <div ref={menuRef} className="relative mx-auto max-w-5xl">
        <div className="liquid-glass mx-auto flex max-w-5xl items-center justify-between rounded-full px-6 py-3">
          <div className="flex items-center gap-8">
            <a href="#" className="group flex items-center gap-2 text-white">
              <span className="relative grid place-items-center">
                <span className="accent-dot absolute inset-0 rounded-full opacity-60 blur-md transition-opacity group-hover:opacity-100" />
                <Globe size={24} className="relative transition-transform duration-700 group-hover:rotate-[180deg]" />
              </span>
              <span className="text-lg font-semibold tracking-tight">Asme</span>
            </a>

            <div className="relative hidden items-center gap-1 md:flex" onMouseLeave={() => setPill(null)}>
              <span
                aria-hidden="true"
                className="absolute top-1/2 h-8 -translate-y-1/2 rounded-full bg-white/10 transition-all duration-300 ease-out"
                style={{
                  left: pill?.left ?? 0,
                  width: pill?.width ?? 0,
                  opacity: pill ? 1 : 0,
                }}
              />
              {LINKS.map((link) => (
                <a
                  key={link}
                  href={`#${link.toLowerCase()}`}
                  onMouseEnter={(e) => track(e.currentTarget)}
                  onFocus={(e) => track(e.currentTarget)}
                  onBlur={() => setPill(null)}
                  className="relative rounded-full px-4 py-1.5 text-sm font-medium text-white/80 outline-none transition-colors hover:text-white focus-visible:text-white"
                >
                  {link}
                </a>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-4">
            <button className="hidden text-sm font-medium text-white transition-opacity hover:opacity-80 sm:inline">
              Sign Up
            </button>
            <button className="liquid-glass rounded-full px-6 py-2 text-sm font-medium text-white transition-colors hover:bg-white/5">
              Login
            </button>
            <button
              onClick={() => setMenuOpen((o) => !o)}
              aria-label={menuOpen ? 'Close menu' : 'Open menu'}
              aria-expanded={menuOpen}
              className="-mr-2 grid h-9 w-9 place-items-center rounded-full text-white/80 transition-colors hover:bg-white/10 hover:text-white md:hidden"
            >
              {menuOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
          </div>
        </div>

        {menuOpen && (
          <div className="glass-panel sheet-in liquid-glass absolute inset-x-0 top-full mt-3 rounded-3xl p-2 md:hidden">
            {[...LINKS, 'Sign Up'].map((link, i) => (
              <a
                key={link}
                href={`#${link.toLowerCase().replace(' ', '-')}`}
                onClick={() => setMenuOpen(false)}
                className="reveal flex items-center justify-between rounded-2xl px-4 py-3.5 text-base font-medium text-white/85 transition-colors hover:bg-white/5 hover:text-white"
                style={{ ['--d' as string]: `${i * 50}ms`, animationDuration: '500ms' }}
              >
                {link}
                <span className="h-1.5 w-1.5 rounded-full bg-[rgb(var(--a1))]" />
              </a>
            ))}
          </div>
        )}
      </div>
    </nav>
  );
}
