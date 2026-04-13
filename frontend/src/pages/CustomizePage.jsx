import CustomizationPanel from "../components/CustomizationPanel";

function CustomizePage({
  game,
  onApplyBasic,
  onApplyPieceCustomization,
  onApplyRuleBuilder,
  onApplyRaw,
  onCreateNewGame,
}) {
  return (
    <main className="customize-layout">
      <CustomizationPanel
        game={game}
        onApplyBasic={onApplyBasic}
        onApplyPieceCustomization={onApplyPieceCustomization}
        onApplyRuleBuilder={onApplyRuleBuilder}
        onApplyRaw={onApplyRaw}
        onCreateNewGame={onCreateNewGame}
      />
    </main>
  );
}

export default CustomizePage;
