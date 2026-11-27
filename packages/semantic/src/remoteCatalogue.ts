import type {
  Iri,
  ArcTypeDefinition,
  BaseEntityDefinition,
  DomainDefinition,
  GraphicalDefinition,
  NodeGraphicalDefinition,
  SemanticAttribute,
  SemanticCatalogue,
  TokenDefinition,
} from './contracts'
import { arcTypeIri } from './iris'

// ---------------------------------------------------------------------------
// Ontology-backed catalogue
//
// Loads entity types, domains, tokens and connection rules from the ontology
// service and exposes them through the synchronous ``SemanticCatalogue``
// interface (the palette and connection service read synchronously — the
// fetch happens once up front in ``load``).
//
// Mapping notes:
// - Entity ``branch`` (a top-level domain branch label, e.g. "physical")
//   resolves to that domain's IRI → ``domainTypeIris`` — this is what the
//   domain-based ``resolve-connection`` endpoint matches on.
// - Arc types are synthesised from rule ``carrier`` values as
//   ``promo#ArcType/<carrier>`` — the server supplies ``arc_type_iri``
//   on each rule record; the ``arcTypeIri()`` helper (iris.ts) is the
//   single shape definition for offline fallback.
// - Graphical definitions are still frontend data (the ontology does not
//   store shapes yet — the future graphic-object editor will own them).
//   They are assigned by entity-type ARCHETYPE: each entity type walks
//   its ``promo:parent`` chain to the seeded fundamental type
//   (environment / lumped / distributed / point / transport_system /
//   info_*) and inherits that archetype's graphic.  Arc types map by
//   carrier (token-flow solid, access/signal dashed).
// ---------------------------------------------------------------------------

/** Vocabulary root the archetype local names are minted under —
 *  etype IRIs look like ``{base}#etype_<archetype>``. */
const ETYPES: Record<string, string> = {
  environment: 'etype_environment',
  lumped: 'etype_lumped',
  distributed: 'etype_distributed',
  point: 'etype_point',
  transport_system: 'etype_transport_system',
  info_constant: 'etype_info_constant',
  info_dynamic: 'etype_info_dynamic',
  info_event: 'etype_info_event',
}

/** Archetype → node graphic.  The env glyph is a ring — a boundary
 *  shell around the model.  Info types carry dashed outlines to mark
 *  the information domain. */
const ARCHETYPE_GRAPHICALS: Record<string, NodeGraphicalDefinition> = {
  environment: {
    iri: 'https://w3id.org/promo#Graphical/environment',
    kind: 'node', shape: 'ring',
    fill: '#f4f6f7', stroke: '#5d6d7e', strokeWidth: 2, radius: 32,
    innerRadius: 28, attributes: [],
  },
  lumped: {
    iri: 'https://w3id.org/promo#Graphical/lumped',
    kind: 'node', shape: 'circle',
    fill: '#d4edda', stroke: '#155724', strokeWidth: 2, radius: 24,
    attributes: [],
  },
  distributed: {
    iri: 'https://w3id.org/promo#Graphical/distributed',
    kind: 'node', shape: 'ellipse',
    fill: '#fff3cd', stroke: '#856404', strokeWidth: 2, width: 72, height: 44,
    attributes: [],
  },
  point: {
    iri: 'https://w3id.org/promo#Graphical/point',
    kind: 'node', shape: 'circle',
    fill: '#f8f9fa', stroke: '#616a6b', strokeWidth: 2, radius: 12,
    attributes: [],
  },
  transport_system: {
    iri: 'https://w3id.org/promo#Graphical/transport_system',
    kind: 'node', shape: 'rectangle',
    fill: '#e8f4fd', stroke: '#2980b9', strokeWidth: 2, width: 56, height: 40,
    attributes: [],
  },
  info_constant: {
    iri: 'https://w3id.org/promo#Graphical/info_constant',
    kind: 'node', shape: 'circle',
    fill: '#f8f9fa', stroke: '#616a6b', strokeWidth: 2, strokeDash: [5, 3],
    radius: 12, attributes: [],
  },
  info_dynamic: {
    iri: 'https://w3id.org/promo#Graphical/info_dynamic',
    kind: 'node', shape: 'roundedRectangle',
    fill: '#f8f9fa', stroke: '#616a6b', strokeWidth: 2, strokeDash: [5, 3],
    width: 56, height: 36, attributes: [],
  },
  info_event: {
    iri: 'https://w3id.org/promo#Graphical/info_event',
    kind: 'node', shape: 'diamond',
    fill: '#f8f9fa', stroke: '#616a6b', strokeWidth: 2, strokeDash: [5, 3],
    width: 48, height: 32, attributes: [],
  },
}

/** Carrier → arc line style: token-flow reads as the substance link;
 *  access/signal arcs are dashed/dotted information links. */
const CARRIER_STYLES: Record<string, { stroke: string; strokeWidth: number; dash?: number[] }> = {
  'token-flow': { stroke: '#333', strokeWidth: 2 },
  access: { stroke: '#7f8c8d', strokeWidth: 1.5, dash: [6, 4] },
  signal: { stroke: '#7f8c8d', strokeWidth: 1.5, dash: [2, 3] },
  reference: { stroke: '#7f8c8d', strokeWidth: 1.5, dash: [8, 4, 2, 4] },
}

function localFrag(iri: string): string {
  return iri.split('#').pop() ?? iri
}

/** Backend record shapes (subset of fields the catalogue consumes). */
export interface EntityTypeRecord {
  iri: string
  label: string
  temporal_type?: string
  spatial_type?: string | null
  spatial_size?: string | null
  branch?: string
  scale_values?: string[]
  description?: string
  parent?: string | null
  /** §20 capability fragments (species_source | reaction_host |
   *  species_transport), resolved through parent ancestry. */
  capabilities?: string[]
}

export interface DomainRecord {
  iri: string
  name: string
  label?: string | null
  parent?: string | null
  branch?: string | null
  tokens?: string[]
  inherited_tokens?: string[]
}

export interface TokenRecord {
  iri: string
  label: string
  parent?: string | null
  kind?: string | null
}

export interface ConnectionRuleRecord {
  iri: string
  rule_type: string
  carrier?: string | null
  /** Server-synthesised ``promo#ArcType/<carrier>`` (§26) — preferred
   *  over local synthesis when present. */
  arc_type_iri?: string | null
}

export interface CatalogueFetchers {
  entityTypes(): Promise<EntityTypeRecord[]>
  domains(): Promise<DomainRecord[]>
  tokens(): Promise<TokenRecord[]>
  connectionRules(): Promise<ConnectionRuleRecord[]>
}

export class RemoteCatalogue implements SemanticCatalogue {
  private entities = new Map<Iri, BaseEntityDefinition>()
  private arcTypes = new Map<Iri, ArcTypeDefinition>()
  private domains = new Map<Iri, DomainDefinition>()
  private tokens = new Map<Iri, TokenDefinition>()
  private graphicals = new Map<Iri, GraphicalDefinition>()

  private constructor(private fallback: SemanticCatalogue) {}

  /** Fetch all records and build the catalogue.  Returns ``fallback``
   *  unchanged when the backend is unreachable. */
  static async load(
    fetchers: CatalogueFetchers,
    fallback: SemanticCatalogue,
  ): Promise<SemanticCatalogue> {
    let entityTypes: EntityTypeRecord[]
    let domains: DomainRecord[]
    let tokens: TokenRecord[]
    let rules: ConnectionRuleRecord[]
    try {
      ;[entityTypes, domains, tokens, rules] = await Promise.all([
        fetchers.entityTypes(),
        fetchers.domains(),
        fetchers.tokens(),
        fetchers.connectionRules(),
      ])
    } catch {
      return fallback
    }

    const cat = new RemoteCatalogue(fallback)

    // branch label -> top-level domain IRI
    const branchDomain = new Map<string, Iri>()
    for (const d of domains) {
      if (d.branch) branchDomain.set(d.branch, d.iri)
      cat.domains.set(d.iri, {
        iri: d.iri,
        label: d.label || d.name,
        typeIris: [d.iri],
        attributes: [],
      })
    }

    for (const t of tokens) {
      cat.tokens.set(t.iri, {
        iri: t.iri,
        label: t.label,
        typeIris: [t.iri],
        attributes: [],
      })
    }

    // Register archetype node graphicals locally (own map wins over
    // the fallback in getGraphicalDefinition).
    for (const g of Object.values(ARCHETYPE_GRAPHICALS)) {
      cat.graphicals.set(g.iri, g)
    }

    // parent chain for the archetype walk
    const parentOf = new Map<Iri, Iri | undefined>(
      entityTypes.map((e) => [e.iri, e.parent ?? undefined]),
    )
    const archetypeOf = (iri: string): string | undefined => {
      let cur: string | undefined = iri
      const seen = new Set<string>()
      while (cur && !seen.has(cur)) {
        const frag = localFrag(cur)
        for (const [archetype, etypeFrag] of Object.entries(ETYPES)) {
          if (frag === etypeFrag) return archetype
        }
        seen.add(cur)
        cur = parentOf.get(cur)
      }
      return undefined
    }

    entityTypes.forEach((e) => {
      const attributes: SemanticAttribute[] = []
      if (e.temporal_type) {
        attributes.push({ predicateIri: 'https://w3id.org/promo#temporalType', value: e.temporal_type })
      }
      if (e.spatial_type) {
        attributes.push({ predicateIri: 'https://w3id.org/promo#spatialType', value: e.spatial_type })
      }
      if (e.spatial_size) {
        attributes.push({ predicateIri: 'https://w3id.org/promo#spatialSize', value: e.spatial_size })
      }
      const domainIri = e.branch ? branchDomain.get(e.branch) : undefined
      cat.entities.set(e.iri, {
        iri: e.iri,
        label: e.label,
        typeIris: [e.iri],
        domainTypeIris: domainIri ? [domainIri] : [],
        parentIri: e.parent ?? undefined,
        graphicalDefinitionIri:
          ARCHETYPE_GRAPHICALS[archetypeOf(e.iri) ?? '']?.iri,
        classifications: [],
        attributes,
      })
    })

    // Arc types from rule carriers: promo#ArcType/<carrier>
    const carriers = [...new Set(rules.map((r) => r.carrier).filter((c): c is string => !!c))]
    const carrierIris = new Map(
      rules.map((r) => [r.carrier, r.arc_type_iri]),
    )
    carriers.forEach((carrier) => {
      const iri = carrierIris.get(carrier) ?? arcTypeIri(carrier)
      const style = CARRIER_STYLES[carrier] ?? { stroke: '#333', strokeWidth: 2 }
      const gIri = `https://w3id.org/promo#Graphical/arc_${carrier}`
      cat.graphicals.set(gIri, {
        iri: gIri,
        kind: 'arc',
        lineStyle: style.dash ? 'dashed' : 'solid',
        stroke: style.stroke,
        strokeWidth: style.strokeWidth,
        dash: style.dash,
        arrowHead: 'triangle',
        attributes: [],
      })
      cat.arcTypes.set(iri, {
        iri,
        label: carrier,
        typeIris: [iri],
        graphicalDefinitionIri: gIri,
        attributes: [],
      })
    })

    return cat
  }

  getBaseEntities(): readonly BaseEntityDefinition[] {
    return [...this.entities.values()]
  }

  getBaseEntity(iri: Iri): BaseEntityDefinition | undefined {
    return this.entities.get(iri)
  }

  getArcTypes(): readonly ArcTypeDefinition[] {
    return [...this.arcTypes.values()]
  }

  getArcType(iri: Iri): ArcTypeDefinition | undefined {
    return this.arcTypes.get(iri)
  }

  getDomain(iri: Iri): DomainDefinition | undefined {
    return this.domains.get(iri)
  }

  getToken(iri: Iri): TokenDefinition | undefined {
    return this.tokens.get(iri)
  }

  getGraphicalDefinition(iri: Iri): GraphicalDefinition | undefined {
    return this.graphicals.get(iri) ?? this.fallback.getGraphicalDefinition(iri)
  }
}
