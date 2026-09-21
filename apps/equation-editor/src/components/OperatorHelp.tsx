import { OPERATOR_HELP } from '../operatorHelp'

const cell: React.CSSProperties = {
  padding: '2px 10px 2px 0',
  verticalAlign: 'top',
  whiteSpace: 'nowrap',
}

/** Compact operator reference — toggled by the "?" button in
 *  ExpressionInput.  Stays open while typing so the syntax can be
 *  consulted mid-expression. */
export default function OperatorHelp() {
  return (
    <table
      style={{
        fontSize: 12,
        borderCollapse: 'collapse',
        border: '1px solid #ddd',
        background: '#fafafa',
        padding: 6,
      }}
    >
      <tbody>
        {OPERATOR_HELP.map((h) => (
          <tr key={h.label}>
            <td style={{ ...cell, fontWeight: 'bold' }}>
              <code>{h.label}</code>
            </td>
            <td style={cell}>
              <code>{h.syntax}</code>
            </td>
            <td style={{ ...cell, whiteSpace: 'normal', color: '#444' }}>
              {h.description}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
