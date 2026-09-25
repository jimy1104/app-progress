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

      <div className="relative flex min-h-screen flex-col">
        <Navbar />
        <Hero />
        <SocialBar />
      </div>

      <Personalize prefs={prefs} update={update} reset={reset} />
    </div>
  );
}
