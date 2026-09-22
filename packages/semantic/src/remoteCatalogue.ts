import type {
  Iri,
  ArcTypeDefinition,
  BaseEntityDefinition,
  DomainDefinition,
  EntityInterfaceDefinition,
  GraphicalDefinition,
  SemanticAttribute,
  SemanticCatalogue,
  TokenDefinition,
} from './contracts'

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
//   ``promo:ArcType/<carrier>`` — the same mapping ``RemoteRuleResolver``
//   applies to resolution results.
// - Graphical definitions are delegated to a fallback catalogue (the
//   ontology does not store shapes yet); entities/arc types are assigned
//   the fallback's graphicals round-robin.
// ---------------------------------------------------------------------------

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
}

export interface CatalogueFetchers {
  entityTypes(): Promise<EntityTypeRecord[]>
  domains(): Promise<DomainRecord[]>
  tokens(): Promise<TokenRecord[]>
  connectionRules(): Promise<ConnectionRuleRecord[]>
}

const ARC_TYPE_PREFIX = 'promo:ArcType/'

export class RemoteCatalogue implements SemanticCatalogue {
  private entities = new Map<Iri, BaseEntityDefinition>()
  private arcTypes = new Map<Iri, ArcTypeDefinition>()
  private domains = new Map<Iri, DomainDefinition>()
  private tokens = new Map<Iri, TokenDefinition>()

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

    const nodeGraphicals = fallback.getBaseEntities()
      .map((e) => e.graphicalDefinitionIri)
      .filter((g): g is Iri => !!g)

    entityTypes.forEach((e, i) => {
      const attributes: SemanticAttribute[] = []
      if (e.temporal_type) {
        attributes.push({ predicateIri: 'promo:temporalType', value: e.temporal_type })
      }
      if (e.spatial_type) {
        attributes.push({ predicateIri: 'promo:spatialType', value: e.spatial_type })
      }
      if (e.spatial_size) {
        attributes.push({ predicateIri: 'promo:spatialSize', value: e.spatial_size })
      }
      const domainIri = e.branch ? branchDomain.get(e.branch) : undefined
      cat.entities.set(e.iri, {
        iri: e.iri,
        label: e.label,
        typeIris: [e.iri],
        domainTypeIris: domainIri ? [domainIri] : [],
        parentIri: e.parent ?? undefined,
        graphicalDefinitionIri: nodeGraphicals.length
          ? nodeGraphicals[i % nodeGraphicals.length]
          : undefined,
        classifications: [],
        attributes,
      })
    })

    // Arc types from rule carriers: promo:ArcType/<carrier>
    const arcGraphicals = fallback.getArcTypes()
      .map((a) => a.graphicalDefinitionIri)
      .filter((g): g is Iri => !!g)
    const carriers = [...new Set(rules.map((r) => r.carrier).filter((c): c is string => !!c))]
    carriers.forEach((carrier, i) => {
      const iri = `${ARC_TYPE_PREFIX}${carrier}`
      cat.arcTypes.set(iri, {
        iri,
        label: carrier,
        typeIris: [iri],
        graphicalDefinitionIri: arcGraphicals.length
          ? arcGraphicals[i % arcGraphicals.length]
          : undefined,
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

  getInterface(_iri: Iri): EntityInterfaceDefinition | undefined {
    return undefined
  }

  getGraphicalDefinition(iri: Iri): GraphicalDefinition | undefined {
    return this.fallback.getGraphicalDefinition(iri)
  }
}
