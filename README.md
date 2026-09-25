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
- **Cinematic intro**: letterbox bars open on load; a soft light trails the cursor; key buttons lean toward the pointer.
- **Motion**: letter-by-letter headline reveal, gradient "curious" with a hand-drawn underline, staggered entrances, drifting aurora colour grade and film grain.
- **Friendly subscribe flow**: validation with shake + hint, loading spinner, success state with a small celebratory burst.
- **Personalize panel** (bottom-right): 4 colour moods, larger text, high contrast, animations on/off, background video on/off — saved in the browser. Respects the OS "reduce motion" setting.
- **Guided first visit**: a one-time tip points to Personalize; "Sign Up" jumps to the email field; a soft light sweep highlights the main action.
- **Keyboard friendly**: visible accent focus rings; Escape closes menus and returns focus.
