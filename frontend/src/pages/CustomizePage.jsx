import LandingNav from "../components/LandingNav";
import CustomizationPanel from "../components/CustomizationPanel";

function CustomizePage({ onCreate, onPlay, initialPreset = "" }) {
  return (
    <main className="customize-page-shell">
      <LandingNav active="customize" onPlay={onPlay} onCustomize={() => {}} />
      <CustomizationPanel onCreate={onCreate} initialPreset={initialPreset} />
    </main>
  );
}

export default CustomizePage;
