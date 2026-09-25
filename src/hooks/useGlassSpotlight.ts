import { useEffect } from 'react';

/**
 * Feeds the pointer position into every `.liquid-glass` element as
 * `--mx` / `--my`, so the glass lights up where the cursor is. The page-level
 * position is also exposed on <html> as `--px` / `--py` for the ambient glow.
 */
export function useGlassSpotlight() {
  useEffect(() => {
    let frame = 0;
    let x = 0;
    let y = 0;

    const paint = () => {
      frame = 0;
      document.documentElement.style.setProperty('--px', `${x}px`);
      document.documentElement.style.setProperty('--py', `${y}px`);
      document.querySelectorAll<HTMLElement>('.liquid-glass').forEach((el) => {
        const r = el.getBoundingClientRect();
        el.style.setProperty('--mx', `${x - r.left}px`);
        el.style.setProperty('--my', `${y - r.top}px`);
      });
    };

    const onMove = (e: PointerEvent) => {
      x = e.clientX;
      y = e.clientY;
      if (!frame) frame = requestAnimationFrame(paint);
    };

    window.addEventListener('pointermove', onMove, { passive: true });
    return () => {
      window.removeEventListener('pointermove', onMove);
      if (frame) cancelAnimationFrame(frame);
    };
  }, []);
}
