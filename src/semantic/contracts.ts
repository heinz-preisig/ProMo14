export type Iri = string

export type SemanticValue = string | number | boolean | null | Iri | SemanticValue[]

export interface SemanticAttribute {
  predicateIri: Iri
  value: SemanticValue
}

export interface Classification {
  dimensionIri: Iri
  valueIri: Iri
}

export interface DomainDefinition {
  iri: Iri
  label: string
  typeIris: Iri[]
  attributes: SemanticAttribute[]
}

export interface TokenDefinition {
  iri: Iri
  label: string
  typeIris: Iri[]
  attributes: SemanticAttribute[]
}

export type PortDirection = 'input' | 'output' | 'bidirectional'

export interface InterfacePortDefinition {
  iri: Iri
  label: string
  direction: PortDirection
  tokenTypeIris: Iri[]
  attributes: SemanticAttribute[]
}

export interface EntityInterfaceDefinition {
  iri: Iri
  ports: InterfacePortDefinition[]
}

export interface BaseEntityDefinition {
  iri: Iri
  label: string
  typeIris: Iri[]
  interfaceIri?: Iri
  graphicalDefinitionIri?: Iri
  classifications: Classification[]
  attributes: SemanticAttribute[]
}

export interface ArcTypeDefinition {
  iri: Iri
  label: string
  typeIris: Iri[]
  graphicalDefinitionIri?: Iri
  attributes: SemanticAttribute[]
}

export type NodeShape = 'circle' | 'rectangle' | 'roundedRectangle' | 'diamond' | 'symbol'
export type ArcLineStyle = 'solid' | 'dashed' | 'dotted'
export type ArrowHead = 'none' | 'triangle' | 'diamond' | 'circle'

export interface NodeGraphicalDefinition {
  iri: Iri
  kind: 'node'
  shape: NodeShape
  fill: string
  stroke: string
  strokeWidth: number
  width?: number
  height?: number
  radius?: number
  symbolIri?: Iri
  attributes: SemanticAttribute[]
}

export interface ArcGraphicalDefinition {
  iri: Iri
  kind: 'arc'
  lineStyle: ArcLineStyle
  stroke: string
  strokeWidth: number
  dash?: number[]
  arrowHead: ArrowHead
  attributes: SemanticAttribute[]
}

export type GraphicalDefinition = NodeGraphicalDefinition | ArcGraphicalDefinition

export type DomainRelation = 'internal' | 'crossDomain'

export interface ConnectionRuleQuery {
  sourceEntityTypeIris: Iri[]
  targetEntityTypeIris: Iri[]
  sourceDomainTypeIris: Iri[]
  targetDomainTypeIris: Iri[]
  sourceTokenTypeIris: Iri[]
  targetTokenTypeIris: Iri[]
  domainRelation: DomainRelation
}

export interface AllowedConnection {
  ruleIri: Iri
  arcTypeIri: Iri
  sourcePortIri?: Iri
  targetPortIri?: Iri
}

export type ConnectionRuleResult =
  | { status: 'forbidden'; reason?: string }
  | { status: 'allowed'; connections: AllowedConnection[] }

export interface SemanticCatalogue {
  getBaseEntities(): readonly BaseEntityDefinition[]
  getBaseEntity(iri: Iri): BaseEntityDefinition | undefined
  getArcTypes(): readonly ArcTypeDefinition[]
  getArcType(iri: Iri): ArcTypeDefinition | undefined
  getDomain(iri: Iri): DomainDefinition | undefined
  getToken(iri: Iri): TokenDefinition | undefined
  getInterface(iri: Iri): EntityInterfaceDefinition | undefined
  getGraphicalDefinition(iri: Iri): GraphicalDefinition | undefined
}

export interface ConnectionRuleResolver {
  resolve(query: ConnectionRuleQuery): ConnectionRuleResult
}
