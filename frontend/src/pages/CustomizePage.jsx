import CustomizationPanel from "../components/CustomizationPanel";

function CustomizePage({
  game,
  onApplyBasic,
  onApplyBoardLayout,
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
        onApplyBoardLayout={onApplyBoardLayout}
        onApplyPieceCustomization={onApplyPieceCustomization}
        onApplyRuleBuilder={onApplyRuleBuilder}
        onApplyRaw={onApplyRaw}
        onCreateNewGame={onCreateNewGame}
      />
    </main>
  );
}

export default CustomizePage;
