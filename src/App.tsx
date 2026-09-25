import BackgroundVideo from './components/BackgroundVideo';
import Navbar from './components/Navbar';
import Hero from './components/Hero';
import SocialBar from './components/SocialBar';
import Personalize from './components/Personalize';
import { usePreferences } from './hooks/usePreferences';
import { useGlassSpotlight } from './hooks/useGlassSpotlight';

export default function App() {
  const { prefs, update, reset } = usePreferences();
  useGlassSpotlight();

  return (
    <div className="relative min-h-screen overflow-hidden bg-black">
      <BackgroundVideo playing={prefs.video} />

      {/* Ambient light that follows the cursor across the scene */}
      <div aria-hidden="true" className="ambient-glow pointer-events-none fixed inset-0" />

      <div className="relative flex min-h-screen flex-col">
        <Navbar />
        <Hero />
        <SocialBar />
      </div>

      <Personalize prefs={prefs} update={update} reset={reset} />

      {/* Cinematic letterbox that opens on load */}
      <div aria-hidden="true" className="letterbox-top pointer-events-none fixed inset-x-0 top-0 z-50 h-[14vh] bg-black" />
      <div aria-hidden="true" className="letterbox-bottom pointer-events-none fixed inset-x-0 bottom-0 z-50 h-[14vh] bg-black" />
    </div>
  );
}
