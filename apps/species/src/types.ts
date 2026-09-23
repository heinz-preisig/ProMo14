/** Mirrors backend/species/service.py document schema (§20). */

export interface ComponentDoc {
  iri: string
  label: string
}

export interface AllocationDoc {
  iri: string
  label: string
  members: string[] // Component IRIs
}

export interface ReactionDoc {
  iri: string
  label: string
  reactants: string[] // Component IRIs
  products: string[] // Component IRIs
  /** member IRI → coefficient (positive; sign from membership,
   *  missing = 1).  The scheme's stoichiometric slots — values bind
   *  into kinetic equations at instantiation (§20). */
  stoichiometry?: Record<string, number>
}

export interface SpeciesDocument {
  components: ComponentDoc[]
  allocations: AllocationDoc[]
  reactions: ReactionDoc[]
}
