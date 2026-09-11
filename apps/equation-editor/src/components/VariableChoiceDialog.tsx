export interface VariableChoiceDialogProps {
  open: boolean
  onClose: () => void
  onChoosePort: () => void
  onChooseDependent: () => void
}

export default function VariableChoiceDialog({
  open,
  onClose,
  onChoosePort,
  onChooseDependent,
}: VariableChoiceDialogProps) {
  if (!open) return null

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.4)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        style={{
          width: 320,
          background: '#fff',
          borderRadius: 6,
          padding: 20,
          boxShadow: '0 4px 20px rgba(0,0,0,0.2)',
          fontSize: 13,
        }}
      >
        <h3 style={{ margin: '0 0 16px' }}>New variable</h3>
        <p style={{ margin: '0 0 16px', color: '#555' }}>
          Choose the kind of variable you want to define.
        </p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <button
            type="button"
            onClick={() => {
              onClose()
              onChoosePort()
            }}
          >
            Port variable
          </button>
          <button
            type="button"
            onClick={() => {
              onClose()
              onChooseDependent()
            }}
          >
            Dependent variable
          </button>
          <button type="button" onClick={onClose} style={{ marginTop: 8 }}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}
