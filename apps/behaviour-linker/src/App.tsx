import 'katex/dist/katex.min.css'
import { Header } from './components/Header'
import { Sidebar } from './components/Sidebar'
import { BaseEquationPanel } from './components/panels/BaseEquationPanel'
import { ComputationSequencePanel } from './components/panels/ComputationSequencePanel'
import { PrintablePanel } from './components/panels/PrintablePanel'
import { ProblemsPanel } from './components/panels/ProblemsPanel'
import { RolesPanel } from './components/panels/RolesPanel'
import { SuggestedEquationsPanel } from './components/panels/SuggestedEquationsPanel'
import { UnresolvedInputsPanel } from './components/panels/UnresolvedInputsPanel'
import { useBehaviourLinker } from './hooks/useBehaviourLinker'

export default function App() {
  const bl = useBehaviourLinker()

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <Header
        title={bl.title}
        report={bl.report}
        entityType={bl.entityType}
        dirty={bl.dirty}
        hasUnsavedChanges={bl.hasUnsavedChanges}
        saveMsg={bl.saveMsg}
        onSave={bl.save}
        onDelete={bl.remove}
      />
      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        <Sidebar
          orderedTypes={bl.orderedTypes}
          selected={bl.entityType}
          onSelect={bl.setEntityType}
          filter={bl.typeFilter}
          onFilterChange={bl.setTypeFilter}
          assignmentByType={bl.assignmentByType}
        />
        <main style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
          {!bl.entityType && (
            <div style={{ color: '#888', fontSize: 13 }}>
              Select an entity type to link its behaviour.
            </div>
          )}
          {bl.entityType && (
            <>
              <BaseEquationPanel
                ctx={bl.ctx}
                baseEquation={bl.baseEquation}
                baseMode={bl.baseMode}
                onPickBase={bl.pickBase}
                onSetMode={bl.setBaseMode}
                lab={bl.lab}
              />
              <ComputationSequencePanel
                sequence={bl.sequence}
                baseEquation={bl.baseEquation}
                report={bl.report}
                eqs={bl.eqs}
                lab={bl.lab}
                onRemove={bl.removeEq}
                onMove={bl.move}
                dragIri={bl.dragIri}
                setDragIri={bl.setDragIri}
                dropTarget={bl.dropTarget}
                setDropTarget={bl.setDropTarget}
                dropOn={bl.dropOn}
              />
              <SuggestedEquationsPanel
                frontier={bl.report?.frontier ?? []}
                eqs={bl.eqs}
                lab={bl.lab}
                onResolve={bl.resolveWith}
              />
              <UnresolvedInputsPanel
                unresolved={bl.report?.unresolved ?? []}
                report={bl.report}
                eqs={bl.eqs}
                lab={bl.lab}
                onResolve={bl.resolveWith}
                onMark={bl.mark}
              />
              <RolesPanel
                report={bl.report}
                eqs={bl.eqs}
                instantiated={bl.instantiated}
                ports={bl.ports}
                variables={bl.ctx?.variables ?? []}
                lab={bl.lab}
                onUnmark={bl.unmark}
                onMark={bl.mark}
                onResolve={bl.resolveWith}
              />
              <PrintablePanel
                previewHtml={bl.previewHtml}
                source={bl.printableLatex}
                copied={bl.copied}
                showSource={bl.showSource}
                onToggleSource={() => bl.setShowSource((s) => !s)}
                onCopy={bl.copyLatex}
                onPrint={bl.printRepresentation}
              />
              <ProblemsPanel report={bl.report} lab={bl.lab} eqLhs={bl.eqLhs} />
            </>
          )}
        </main>
      </div>
    </div>
  )
}
