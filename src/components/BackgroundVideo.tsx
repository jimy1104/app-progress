import { useCallback, useEffect, useRef } from 'react';

const VIDEO_SRC =
  'https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260328_115001_bcdaa3b4-03de-47e7-ad63-ae3e392c32d4.mp4';

const FADE_MS = 500;
const FADE_OUT_BEFORE_END = 0.55;

interface Props {
  playing: boolean;
}

export default function BackgroundVideo({ playing }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const frameRef = useRef<number | null>(null);
  const fadingOutRef = useRef(false);
  const restartRef = useRef<number | null>(null);

  const cancelFade = () => {
    if (frameRef.current !== null) {
      cancelAnimationFrame(frameRef.current);
      frameRef.current = null;
    }
  };

  // rAF-driven fade that resumes from whatever opacity the video currently has.
  const fadeTo = useCallback((target: number) => {
    const video = videoRef.current;
    if (!video) return;
    cancelFade();

    const from = parseFloat(video.style.opacity || '0');
    const start = performance.now();

    const step = (now: number) => {
      const t = Math.min((now - start) / FADE_MS, 1);
      video.style.opacity = String(from + (target - from) * t);
      frameRef.current = t < 1 ? requestAnimationFrame(step) : null;
    };
    frameRef.current = requestAnimationFrame(step);
  }, []);

  const handleLoaded = () => {
    fadingOutRef.current = false;
    fadeTo(1);
  };

  const handleTimeUpdate = () => {
    const video = videoRef.current;
    if (!video || !video.duration || fadingOutRef.current) return;
    if (video.duration - video.currentTime <= FADE_OUT_BEFORE_END) {
      fadingOutRef.current = true;
      fadeTo(0);
    }
  };

  const handleEnded = () => {
    const video = videoRef.current;
    if (!video) return;
    cancelFade();
    video.style.opacity = '0';
    restartRef.current = window.setTimeout(() => {
      video.currentTime = 0;
      video.play().catch(() => {});
      fadingOutRef.current = false;
      fadeTo(1);
    }, 100);
  };

  // Play / pause from the personalize panel.
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    if (playing) video.play().catch(() => {});
    else video.pause();
  }, [playing]);

  useEffect(
    () => () => {
      cancelFade();
      if (restartRef.current !== null) clearTimeout(restartRef.current);
    },
    [],
  );

  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
      <video
        ref={videoRef}
        src={VIDEO_SRC}
        className="absolute inset-0 h-full w-full translate-y-[17%] object-cover"
        style={{ opacity: 0 }}
        autoPlay
        muted
        playsInline
        preload="auto"
        onLoadedData={handleLoaded}
        onTimeUpdate={handleTimeUpdate}
        onEnded={handleEnded}
      />

      {/* Colour grade: accent-tinted aurora drifting over the footage */}
      <div className="aurora-a absolute -left-1/4 top-[-20%] h-[70vmax] w-[70vmax] rounded-full bg-[radial-gradient(circle,rgb(var(--a1)/0.28),transparent_60%)] mix-blend-screen blur-3xl" />
      <div className="aurora-b absolute -right-1/4 bottom-[-30%] h-[65vmax] w-[65vmax] rounded-full bg-[radial-gradient(circle,rgb(var(--a2)/0.26),transparent_60%)] mix-blend-screen blur-3xl" />

      {/* Legibility vignette */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_50%_35%,transparent_0%,rgb(5_6_10/0.35)_55%,rgb(5_6_10/0.9)_100%)]" />
      <div className="absolute inset-x-0 top-0 h-48 bg-gradient-to-b from-black/70 to-transparent" />
      <div className="absolute inset-x-0 bottom-0 h-56 bg-gradient-to-t from-black/80 to-transparent" />

      {/* Film grain */}
      <div className="grain absolute -inset-[10%] opacity-[0.07] mix-blend-overlay" />
    </div>
  );
}
