# app-progress

Single-page cinematic hero for **Asme**: looping background video, liquid glass UI, animated accents and a personalization panel.

## Stack
Vite · React 18 · TypeScript · Tailwind CSS 3 (default config) · lucide-react

## Run
```bash
npm install
npm run dev      # http://localhost:5173
npm run build
```

## Highlights
- **Background video** with a requestAnimationFrame fade system (fade in on load, fade out 0.55 s before the end, seamless restart).
- **Liquid glass** surfaces with a pointer-following accent light.
- **Motion**: letter-by-letter headline reveal, gradient "curious" with a hand-drawn underline, staggered entrances, drifting aurora colour grade and film grain.
- **Friendly subscribe flow**: validation with shake + hint, loading spinner, success state with a small celebratory burst.
- **Personalize panel** (bottom-right): 4 colour moods, larger text, animations on/off, background video on/off — saved in the browser. Respects the OS "reduce motion" setting.
