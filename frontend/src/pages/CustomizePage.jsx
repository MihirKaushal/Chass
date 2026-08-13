import LandingNav from "../components/LandingNav";
import CustomizationPanel from "../components/CustomizationPanel";
import SiteFooter from "../components/SiteFooter";

function CustomizePage({ onCreate, onPlay, initialPreset = "" }) {
  return (
    <div className="page-frame">
      <main className="customize-page-shell">
        <LandingNav active="customize" onPlay={onPlay} onCustomize={() => {}} />
        <CustomizationPanel onCreate={onCreate} initialPreset={initialPreset} />
      </main>
      <SiteFooter />
    </div>
  );
}

export default CustomizePage;
