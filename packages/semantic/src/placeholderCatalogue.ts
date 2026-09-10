import type {
  Iri,
  BaseEntityDefinition,
  ArcTypeDefinition,
  NodeGraphicalDefinition,
  ArcGraphicalDefinition,
  GraphicalDefinition,
  SemanticCatalogue,
  ConnectionRuleResolver,
  ConnectionRuleQuery,
  ConnectionRuleResult,
} from './contracts'

// ---------------------------------------------------------------------------
// Placeholder graphical definitions (mirror the old hard-coded styles)
// ---------------------------------------------------------------------------

const nodeGraphicalA: NodeGraphicalDefinition = {
  iri: 'promo:Graphical/TypeA',
  kind: 'node',
  shape: 'circle',
  fill: '#e8f4fd',
  stroke: '#2980b9',
  strokeWidth: 2,
  radius: 24,
  attributes: [],
}

const nodeGraphicalB: NodeGraphicalDefinition = {
  iri: 'promo:Graphical/TypeB',
  kind: 'node',
  shape: 'circle',
  fill: '#d4edda',
  stroke: '#155724',
  strokeWidth: 2,
  radius: 24,
  attributes: [],
}

const nodeGraphicalC: NodeGraphicalDefinition = {
  iri: 'promo:Graphical/TypeC',
  kind: 'node',
  shape: 'circle',
  fill: '#fff3cd',
  stroke: '#856404',
  strokeWidth: 2,
  radius: 24,
  attributes: [],
}

const arcGraphical1: ArcGraphicalDefinition = {
  iri: 'promo:Graphical/ArcType1',
  kind: 'arc',
  lineStyle: 'solid',
  stroke: '#333',
  strokeWidth: 2,
  arrowHead: 'triangle',
  attributes: [],
}

const arcGraphical2: ArcGraphicalDefinition = {
  iri: 'promo:Graphical/ArcType2',
  kind: 'arc',
  lineStyle: 'dashed',
  stroke: '#888',
  strokeWidth: 2,
  dash: [6, 4],
  arrowHead: 'triangle',
  attributes: [],
}

// ---------------------------------------------------------------------------
// Placeholder base-entity definitions
// ---------------------------------------------------------------------------

const entityA: BaseEntityDefinition = {
  iri: 'promo:TypeA',
  label: 'Type A',
  typeIris: [],
  graphicalDefinitionIri: 'promo:Graphical/TypeA',
  classifications: [],
  attributes: [],
}

const entityB: BaseEntityDefinition = {
  iri: 'promo:TypeB',
  label: 'Type B',
  typeIris: [],
  graphicalDefinitionIri: 'promo:Graphical/TypeB',
  classifications: [],
  attributes: [],
}

const entityC: BaseEntityDefinition = {
  iri: 'promo:TypeC',
  label: 'Type C',
  typeIris: [],
  graphicalDefinitionIri: 'promo:Graphical/TypeC',
  classifications: [],
  attributes: [],
}

// ---------------------------------------------------------------------------
// Placeholder arc-type definitions
// ---------------------------------------------------------------------------

const arcType1: ArcTypeDefinition = {
  iri: 'promo:ArcType1',
  label: 'Arc Type 1',
  typeIris: [],
  graphicalDefinitionIri: 'promo:Graphical/ArcType1',
  attributes: [],
}

const arcType2: ArcTypeDefinition = {
  iri: 'promo:ArcType2',
  label: 'Arc Type 2',
  typeIris: [],
  graphicalDefinitionIri: 'promo:Graphical/ArcType2',
  attributes: [],
}

// ---------------------------------------------------------------------------
// In-memory catalogue
// ---------------------------------------------------------------------------

class PlaceholderCatalogue implements SemanticCatalogue {
  private entities = new Map<Iri, BaseEntityDefinition>([
    [entityA.iri, entityA],
    [entityB.iri, entityB],
    [entityC.iri, entityC],
  ])

  private arcTypeMap = new Map<Iri, ArcTypeDefinition>([
    [arcType1.iri, arcType1],
    [arcType2.iri, arcType2],
  ])

  private graphicals = new Map<Iri, GraphicalDefinition>([
    [nodeGraphicalA.iri, nodeGraphicalA],
    [nodeGraphicalB.iri, nodeGraphicalB],
    [nodeGraphicalC.iri, nodeGraphicalC],
    [arcGraphical1.iri, arcGraphical1],
    [arcGraphical2.iri, arcGraphical2],
  ])

  getBaseEntities(): readonly BaseEntityDefinition[] {
    return [...this.entities.values()]
  }

  getBaseEntity(iri: Iri): BaseEntityDefinition | undefined {
    return this.entities.get(iri)
  }

  getArcTypes(): readonly ArcTypeDefinition[] {
    return [...this.arcTypeMap.values()]
  }

  getArcType(iri: Iri): ArcTypeDefinition | undefined {
    return this.arcTypeMap.get(iri)
  }

  getDomain(): undefined {
    return undefined
  }

  getToken(): undefined {
    return undefined
  }

  getInterface(): undefined {
    return undefined
  }

  getGraphicalDefinition(iri: Iri): GraphicalDefinition | undefined {
    return this.graphicals.get(iri)
  }
}

// ---------------------------------------------------------------------------
// Placeholder connection-rule resolver — allows all connections
// ---------------------------------------------------------------------------

class PlaceholderRuleResolver implements ConnectionRuleResolver {
  resolve(_query: ConnectionRuleQuery): ConnectionRuleResult {
    return {
      status: 'allowed',
      connections: [
        { ruleIri: 'promo:Rule/AllowAll', arcTypeIri: 'promo:ArcType1' },
        { ruleIri: 'promo:Rule/AllowAll', arcTypeIri: 'promo:ArcType2' },
      ],
    }
  }
}

export const placeholderCatalogue = new PlaceholderCatalogue()
export const placeholderRuleResolver = new PlaceholderRuleResolver()
