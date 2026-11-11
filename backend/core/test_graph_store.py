"""Tests for ``backend/core/graph_store.py``."""

import json

from rdflib import BNode, Dataset, Literal, URIRef
from rdflib.namespace import RDF, RDFS

from .graph_store import PROMO, RdfStore

ARTEFACT = "https://example.org/artefact"


def _graph_ids(path):
    """Non-empty graph IRIs in a .trig file."""
    probe = Dataset()
    probe.parse(str(path), format="trig")
    return {str(g.identifier) for g in probe.graphs() if len(g)}


def _store_with_equations(tmp_path, eq_ids):
    store = RdfStore(tmp_path)
    g = store.dataset.get_context(URIRef(ARTEFACT))
    store.add_variable_dict(g, {
        "iri": f"{ARTEFACT}#V_1",
        "label": "rho",
        "internal_id": "V_1",
        "network": "thermo",
        "equations": {
            eq_id: {"iri": "", "internal_id": eq_id, "rhs": "a + b"}
            for eq_id in eq_ids
        },
    })
    return store, g


def _equation_ids(g):
    return {
        str(g.value(s, PROMO["internalID"]))
        for s in g.subjects(RDF.type, PROMO["Equation"])
    }


def test_migrate_equation_ids_renumbers_epoch_ids(tmp_path):
    store, g = _store_with_equations(
        tmp_path, ["E_3", "E_1750000000000", "E_1789990282783"],
    )
    store._migrate_equation_ids()
    # E_3 is conforming and stays; the two epoch ids take the smallest
    # free numbers (sorted by IRI: E_1750… < E_1789…).
    assert _equation_ids(g) == {"E_1", "E_2", "E_3"}
    assert store.dirty


def test_migrate_equation_ids_is_idempotent(tmp_path):
    store, g = _store_with_equations(tmp_path, ["E_1750000000000"])
    store._migrate_equation_ids()
    store.dirty = False
    store._migrate_equation_ids()
    assert _equation_ids(g) == {"E_1"}
    assert not store.dirty


def test_migrate_equation_ids_noop_when_conforming(tmp_path):
    store, g = _store_with_equations(tmp_path, ["E_1", "E_2"])
    store._migrate_equation_ids()
    assert _equation_ids(g) == {"E_1", "E_2"}
    assert not store.dirty


def test_migrate_equation_iris_rehomes_promo_namespace(tmp_path):
    """promo#-minted equation IRIs move into the graph's own namespace
    ({graphIRI}#) — promo# is vocabulary only — and object references
    follow, including references from other graphs (assignment
    sequences)."""
    store = RdfStore(tmp_path)
    g = store.dataset.get_context(URIRef(ARTEFACT))
    var = URIRef(f"{ARTEFACT}#V_1")
    old = URIRef(f"{PROMO}E_7")
    g.add((var, RDF.type, PROMO["Variable"]))
    g.add((old, RDF.type, PROMO["Equation"]))
    g.add((old, PROMO["internalID"], Literal("E_7")))
    g.add((var, PROMO["hasEquation"], old))
    # A reference from a different graph (e.g. an assignment artefact).
    other = store.dataset.get_context(URIRef("https://example.org/asg"))
    res = URIRef("https://example.org/asg#a1")
    other.add((res, PROMO["hasBaseEquation"], old))

    store._migrate_equation_iris()

    new = URIRef(f"{ARTEFACT}#E_7")
    assert (new, RDF.type, PROMO["Equation"]) in g
    assert (old, None, None) not in g
    assert (var, PROMO["hasEquation"], new) in g
    assert (var, PROMO["hasEquation"], old) not in g
    assert (res, PROMO["hasBaseEquation"], new) in other
    assert store.dirty


def test_migrate_equation_iris_noop_when_conforming(tmp_path):
    """Equations minted via add_variable_dict already land under the
    artefact's namespace — the migration is a no-op."""
    store, g = _store_with_equations(tmp_path, ["E_1"])
    store._migrate_equation_iris()
    assert not store.dirty
    assert all(str(s).startswith(ARTEFACT)
               for s in g.subjects(RDF.type, PROMO["Equation"]))


def test_migrate_domain_membership_uses_universe_iri(tmp_path):
    store = RdfStore(tmp_path)
    graph = store.ontology_graph
    root = store.mint_iri(graph.identifier, "domain_root")
    physical = store.mint_iri(graph.identifier, "domain_physical")
    variable = store.mint_iri(graph.identifier, "V_1")
    graph.add((root, RDF.type, PROMO["Domain"]))
    graph.add((root, PROMO["name"], Literal("root")))
    graph.add((physical, RDF.type, PROMO["Domain"]))
    graph.add((physical, PROMO["name"], Literal("physical")))
    graph.add((physical, PROMO["parent"], root))
    graph.add((variable, RDF.type, PROMO["Variable"]))
    graph.add((variable, PROMO["network"], Literal("physical")))

    store._migrate_domain_membership()

    universe = store.mint_iri(graph.identifier, "domain_universe")
    assert (universe, RDF.type, PROMO["Domain"]) in graph
    assert graph.value(universe, PROMO["name"]) == Literal("universe")
    assert graph.value(physical, PROMO["parent"]) == universe
    assert graph.value(variable, PROMO["inDomain"]) == physical

    store.dirty = False
    store._migrate_domain_membership()
    assert not store.dirty


def _store_with_legacy_equation(tmp_path, rhs="rho + rho"):
    """Build a saved artefact containing a literal-only, checkable RHS."""
    store = RdfStore(tmp_path)
    store.load()
    store.create_artefact_graph(
        ARTEFACT,
        "Library",
        uses=[str(store.ONTOLOGY_GRAPH_IRI)],
    )
    graph = store.graph(ARTEFACT)
    store.add_variable_dict(graph, {
        "iri": f"{ARTEFACT}#V_rho",
        "label": "rho",
        "internal_id": "V_1",
        "network": "universe",
        "units": [0] * 8,
    })
    store.add_variable_dict(graph, {
        "iri": f"{ARTEFACT}#V_result",
        "label": "result",
        "internal_id": "V_2",
        "network": "universe",
        "units": [0] * 8,
        "equations": {
            "E_1": {
                "iri": f"{ARTEFACT}#E_1",
                "internal_id": "E_1",
                "rhs": rhs,
                "network": "universe",
            },
        },
    })
    store.save()
    return URIRef(f"{ARTEFACT}#E_1")


def test_load_migrates_literal_rhs_to_canonical_expression(tmp_path):
    equation = _store_with_legacy_equation(tmp_path)

    store = RdfStore(tmp_path)
    store.load()

    graph = store.graph(ARTEFACT)
    canonical = graph.value(equation, PROMO["rhsExpression"])
    assert canonical is not None
    assert graph.value(equation, PROMO["rhs"]) == Literal("( rho + rho )")
    incidence = graph.value(equation, PROMO["incidenceList"])
    assert json.loads(str(incidence)) == [f"{ARTEFACT}#V_1"]
    assert store.dirty


def test_canonical_rhs_migration_leaves_uncheckable_legacy_rhs(tmp_path):
    equation = _store_with_legacy_equation(tmp_path, rhs="missing + rho")

    store = RdfStore(tmp_path)
    store.load()

    graph = store.graph(ARTEFACT)
    assert graph.value(equation, PROMO["rhsExpression"]) is None
    assert graph.value(equation, PROMO["rhs"]) == Literal("missing + rho")


def test_canonical_rhs_migration_is_idempotent(tmp_path):
    equation = _store_with_legacy_equation(tmp_path)
    store = RdfStore(tmp_path)
    store.load()
    canonical = store.graph(ARTEFACT).value(equation, PROMO["rhsExpression"])

    store.dirty = False
    store._migrate_canonical_rhs()

    assert store.graph(ARTEFACT).value(equation, PROMO["rhsExpression"]) == canonical
    assert not store.dirty


def test_save_fans_out_per_artefact_line(tmp_path):
    """Hub #4: save() writes one .trig per artefact line — the draft
    plus its frozen versions — named by the line IRI's last segment."""
    store = RdfStore(tmp_path)
    store.load()  # seeds the ontology line
    store.create_artefact_graph(
        "https://example.org/lib", "Library", label="lib",
        uses=[str(store.ONTOLOGY_GRAPH_IRI)])
    store.freeze_version("1.0", "https://example.org/lib")
    store.save()

    ont = tmp_path / "ontology.trig"
    lib = tmp_path / "lib.trig"
    assert ont.is_file() and lib.is_file()
    # ontology.trig holds only the ontology line; lib.trig holds the
    # draft plus its frozen version ("the file is the history").
    assert _graph_ids(ont) == {str(store.ONTOLOGY_GRAPH_IRI)}
    assert _graph_ids(lib) == {
        "https://example.org/lib", "https://example.org/lib/1.0"}
    assert not store.dirty


def test_load_splits_legacy_single_file(tmp_path):
    """Hub #4 migration: an ontology.trig holding the whole dataset is
    split into per-line files on first load."""
    store = RdfStore(tmp_path)
    store.load()
    store.create_artefact_graph("https://example.org/m", "Model")
    store.save("ontology.trig")  # legacy whole-dataset layout
    assert not (tmp_path / "m.trig").exists()

    fresh = RdfStore(tmp_path)
    fresh.load()
    assert (tmp_path / "m.trig").is_file()
    assert _graph_ids(tmp_path / "ontology.trig") == \
        {str(store.ONTOLOGY_GRAPH_IRI)}
    # the model graph survived the split
    assert len(fresh.dataset.graph(URIRef("https://example.org/m")))


def test_save_removes_stale_line_files(tmp_path):
    """A .trig whose line no longer exists is removed on save."""
    store = RdfStore(tmp_path)
    store.load()
    stale = tmp_path / "ghost.trig"
    stale.write_text(
        "<https://example.org/ghost> { "
        "<https://example.org/ghost> a <urn:x> }")
    store.save()
    assert not stale.exists()

ONTO = "https://w3id.org/promo/ontology"
# §26: variable IRIs live under the owning artefact's namespace —
# seeded factors are ``{ontology}#F_<mech>``.
PVAR = f"{ONTO}#"


def test_seed_mechanism_drives(tmp_path):
    """§32 stage-2: mechanism leaves carry promo:drives — the token
    their driving effort carries — resolving through promo:parent
    ancestry (union, not nearest-wins).  The carried side stays
    promo:token on the grouping types."""
    from .capabilities import mechanism_drives, mechanism_token
    store = RdfStore(tmp_path)
    store.load()
    ont = store.ontology_graph

    expected = {
        "convection_transport": "momentum",
        "diffusion_transport": "component_mass",
        "heat_transport": "energy",
        "radiation_transport": "energy",
        "work_transport": "momentum",
    }
    for frag, tok in expected.items():
        et = URIRef(f"{ONTO}#etype_{frag}")
        assert set(ont.objects(et, PROMO["drives"])) == {
            URIRef(f"{ONTO}#token_{tok}")}, frag
        assert mechanism_drives(store, ont.identifier, str(et)) == {
            f"{ONTO}#token_{tok}"}, frag
        # carries side unchanged: family on the grouping ancestor
        assert mechanism_token(store, ont.identifier, str(et)) is not None

    # Groupings declare no drives themselves; a non-mechanism type
    # resolves nothing.
    assert mechanism_drives(
        store, ont.identifier, f"{ONTO}#etype_mass_transport") == set()
    assert mechanism_drives(
        store, ont.identifier, f"{ONTO}#etype_lumped") == set()

    # Ancestry union: a user subtype inherits its parent's drive and
    # may add a coupled one alongside it.
    sub = URIRef(f"{ONTO}#etype_test_coupled")
    ont.add((sub, RDF.type, PROMO["EntityType"]))
    ont.add((sub, PROMO["parent"],
             URIRef(f"{ONTO}#etype_convection_transport")))
    ont.add((sub, PROMO["drives"], URIRef(f"{ONTO}#token_energy")))
    assert mechanism_drives(store, ont.identifier, str(sub)) == {
        f"{ONTO}#token_momentum", f"{ONTO}#token_energy"}


def test_seed_incidence_factors(tmp_path):
    """§25: one canonical F_<mech> variable per arc sub-index — fixed
    [A_k, N] shape, constant+parameter, dimensionless.  §4 neutrality:
    incidence matrices are structural operators, not physical
    quantities — they carry no token declarations."""
    store = RdfStore(tmp_path)
    store.load()
    ont = store.ontology_graph
    node = URIRef(f"{ONTO}#idx_node")
    arc = URIRef(f"{ONTO}#idx_arc")
    subs = sorted(ont.subjects(PROMO["subIndexOf"], arc))
    assert len(subs) >= 5
    for sub in subs:
        mech = str(ont.value(sub, PROMO["shortName"]))[2:]
        f = URIRef(f"{PVAR}F_{mech}")
        assert (f, RDF.type, PROMO["Variable"]) in ont, mech
        assert str(ont.value(f, RDFS.label)) == f"F_{mech}"
        assert set(ont.objects(f, PROMO["indexStructure"])) == {sub, node}
        assert str(ont.value(f, PROMO["portVariable"])) == "false"
        assert set(ont.objects(f, PROMO["carriesToken"])) == set(), mech
        assert (f, PROMO["tokenVector"], None) not in ont, mech


def test_seed_incidence_factors_strips_legacy_token_decls(tmp_path):
    """§4 migration: pre-neutrality records carrying token
    declarations are stripped on re-seed (load)."""
    store = RdfStore(tmp_path)
    store.load()
    ont = store.ontology_graph
    f = URIRef(f"{PVAR}F_conv")
    ont.add((f, PROMO["carriesToken"],
             URIRef(f"{ONTO}#token_mass")))
    ont.add((f, PROMO["tokenVector"],
             Literal('{"token_mass": 1}')))
    store._seed_incidence_factors(ont, ONTO)
    assert set(ont.objects(f, PROMO["carriesToken"])) == set()
    assert (f, PROMO["tokenVector"], None) not in ont


def test_seed_incidence_factors_rehomes_legacy_spelling(tmp_path):
    """The port-variable-era ``promo:F_conv`` record is rehomed under
    the artefact namespace and normalised — internalID kept."""
    store = RdfStore(tmp_path)
    store.load()
    ont = store.ontology_graph
    legacy = URIRef("promo:F_conv")
    ont.add((legacy, RDF.type, PROMO["Variable"]))
    ont.add((legacy, PROMO["internalID"], Literal("V_4")))
    ont.add((legacy, PROMO["portVariable"], Literal(True)))
    store._seed_incidence_factors(ont, ONTO)
    f = URIRef(f"{PVAR}F_conv")
    assert (legacy, None, None) not in ont
    # §26: deterministic internal ID — the frag is the identity, so
    # ``{graph}#{internal_id}`` reproduces the canonical IRI.
    assert str(ont.value(f, PROMO["internalID"])) == "F_conv"
    assert str(ont.value(f, PROMO["portVariable"])) == "false"
    assert set(ont.objects(f, PROMO["indexStructure"])) == {
        URIRef(f"{ONTO}#idx_arc_convection"), URIRef(f"{ONTO}#idx_node")}


def test_migrate_incidence_factors_strips_duplicate_records(tmp_path):
    """Hand-authored F_* copies in artefact graphs are removed so the
    seeded ontology record is the single description."""
    store = RdfStore(tmp_path)
    store.load()
    dup = URIRef("promo:F_heat")   # the historical duplicate spelling
    g = store.dataset.get_context(URIRef(ARTEFACT))
    store.add_variable_dict(g, {
        "iri": str(dup), "label": "F_heat", "network": "physical"})
    store._migrate_variable_iris()   # rehomes to {artefact}#F_heat
    store._migrate_incidence_factors()
    assert (URIRef(f"{ARTEFACT}#F_heat"), None, None) not in g
    assert (dup, None, None) not in g
    canonical = URIRef(f"{PVAR}F_heat")
    assert (canonical, RDF.type,
            PROMO["Variable"]) in store.ontology_graph


def test_migrate_incidence_factors_strips_absolute_orphans(tmp_path):
    """The vocabulary-ns ``promo#F_*`` spelling is never canonical —
    duplicates under it are orphans even in the ontology graph."""
    store = RdfStore(tmp_path)
    store.load()
    ont = store.ontology_graph
    orphan = PROMO["F_rad"]
    ont.add((orphan, RDF.type, PROMO["Variable"]))
    ont.add((orphan, RDFS.label, Literal("F_rad")))
    store._migrate_incidence_factors()
    assert (orphan, None, None) not in ont
    # …while the canonical artefact-ns record stays.
    assert (URIRef(f"{PVAR}F_rad"), RDF.type,
            PROMO["Variable"]) in ont


def test_migrate_variable_iris_rehomes_and_rewrites(tmp_path):
    """§26: relative ``promo:X`` subjects move under their artefact's
    namespace; object references and literal tokens follow."""
    store = RdfStore(tmp_path)
    store.load()
    g = store.dataset.get_context(URIRef(ARTEFACT))
    var = URIRef("promo:x")
    store.add_variable_dict(g, {
        "iri": str(var), "label": "x", "network": "physical"})
    eq = URIRef(f"{ARTEFACT}#E_1")
    g.add((eq, RDF.type, PROMO["Equation"]))
    g.add((eq, PROMO["lhs"], var))
    g.add((eq, PROMO["incidenceList"],
           Literal('["promo:x", "promo:ghost"]')))
    g.add((URIRef(f"{ARTEFACT}#node"), PROMO["arcType"],
           URIRef("promo:ArcType/token-flow")))
    store._migrate_variable_iris()
    new = URIRef(f"{ARTEFACT}#x")
    assert (var, None, None) not in g
    assert (new, RDF.type, PROMO["Variable"]) in g
    assert (eq, PROMO["lhs"], new) in g
    assert str(g.value(eq, PROMO["incidenceList"])) == \
        f'["{new}", "{PROMO}ghost"]'
    assert (URIRef(f"{ARTEFACT}#node"), PROMO["arcType"],
            PROMO["ArcType/token-flow"]) in g


def test_migrate_variable_iris_consolidates_split_record(tmp_path):
    """A variable written into two graphs merges into the graph that
    holds an equation naming it — the home record wins literal
    conflicts, the foreign copy uniques are absorbed."""
    store = RdfStore(tmp_path)
    store.load()
    ont = store.ontology_graph
    lib = store.dataset.get_context(URIRef(ARTEFACT))
    var = URIRef("promo:heat")
    eq = URIRef(f"{ONTO}#E_9")
    ont.add((eq, RDF.type, PROMO["Equation"]))
    ont.add((eq, PROMO["lhs"], var))
    for g in (ont, lib):
        store.add_variable_dict(g, {
            "iri": str(var), "label": "heat", "network": "physical"})
    lib.add((var, PROMO["doc"], Literal("library doc")))
    ont.add((var, PROMO["doc"], Literal("ontology doc")))
    store._migrate_variable_iris()
    new = URIRef(f"{ONTO}#heat")
    assert (var, None, None) not in ont
    assert (var, None, None) not in lib
    assert (new, RDF.type, PROMO["Variable"]) in ont
    assert (new, None, None) not in lib
    assert str(ont.value(new, PROMO["doc"])) == "ontology doc"
    assert (eq, PROMO["lhs"], new) in ont


def test_heal_vocab_ns_refs_repoints_and_strips(tmp_path):
    """Assignment/canonical references spelt ``promo#X`` heal on load:
    a unique same-local-name subject wins the ref, dead variable role
    claims are stripped, list members and vocabulary terms stay."""
    store = RdfStore(tmp_path)
    store.load()
    ont = store.ontology_graph
    home = URIRef(f"{PVAR}F_conv")
    assert (home, RDF.type, PROMO["Variable"]) in ont
    g = store.dataset.get_context(URIRef(ARTEFACT))
    rec = URIRef(f"{ARTEFACT}#asg_1")
    g.add((rec, RDF.type, PROMO["BehaviourAssignment"]))
    g.add((rec, PROMO["hasInstantiatedVariable"], PROMO["F_conv"]))
    g.add((rec, PROMO["hasInstantiatedVariable"], PROMO["gone"]))
    g.add((rec, PROMO["arcType"], PROMO["ArcType/token-flow"]))
    node = BNode()   # canonical hasArguments list member
    g.add((node, RDF["first"], PROMO["F_conv"]))
    g.add((node, RDF["first"], PROMO["dead"]))
    eq = URIRef(f"{ARTEFACT}#E_1")
    g.add((eq, PROMO["incidenceList"], Literal(f'["{PROMO}F_conv"]')))
    store._heal_vocab_ns_refs()
    assert (rec, PROMO["hasInstantiatedVariable"], home) in g
    assert (rec, PROMO["hasInstantiatedVariable"], PROMO["F_conv"]) not in g
    assert (rec, PROMO["hasInstantiatedVariable"], PROMO["gone"]) not in g
    assert (rec, PROMO["arcType"], PROMO["ArcType/token-flow"]) in g
    assert (node, RDF["first"], home) in g
    assert (node, RDF["first"], PROMO["dead"]) in g   # list stays intact
    assert str(g.value(eq, PROMO["incidenceList"])) == f'["{home}"]'


ONT2 = "https://example.org/ont2"
LIB = "https://example.org/lib"
MODEL = "https://example.org/model"


def test_resolution_scope_is_transitive(tmp_path):
    """§27: pins compose — a model pinning a library sees the
    library's ontology pins, and the ontology's own pins too.
    Self first, then pins breadth-first."""
    store = RdfStore(tmp_path)
    store.load()
    ont2 = URIRef(ONT2)
    base = store.dataset.get_context(ont2)
    # ont2 extends the core ontology
    base.add((ont2, PROMO["usesOntology"], store.ONTOLOGY_GRAPH_IRI))
    store.create_artefact_graph(
        LIB, "Library", uses=[ONT2])
    store.create_artefact_graph(
        MODEL, "Model", uses_library=[LIB])

    scope = [str(i) for i in store.resolution_scope(MODEL)]
    assert scope[0] == MODEL
    assert set(scope) == {
        MODEL, LIB, ONT2, str(store.ONTOLOGY_GRAPH_IRI)}

    # And a library scoped to its own pins sees its ontology set.
    lib_scope = {str(i) for i in store.resolution_scope(LIB)}
    assert lib_scope == {
        LIB, ONT2, str(store.ONTOLOGY_GRAPH_IRI)}


def test_resolution_scope_excludes_resource_pins(tmp_path):
    """usesAssignment / usesSpecies are resource pins consumed by
    their services, not vocabulary — they stay out of the scope."""
    store = RdfStore(tmp_path)
    store.load()
    spec = URIRef("https://example.org/species")
    asg = URIRef("https://example.org/asg")
    store.create_artefact_graph(
        MODEL, "Model", uses=[str(store.ONTOLOGY_GRAPH_IRI)])
    g = store.dataset.get_context(URIRef(MODEL))
    g.add((URIRef(MODEL), PROMO["usesSpecies"], spec))
    g.add((URIRef(MODEL), PROMO["usesAssignment"], asg))
    scope = {str(i) for i in store.resolution_scope(MODEL)}
    assert scope == {MODEL, str(store.ONTOLOGY_GRAPH_IRI)}


def test_resolution_scope_cycle_safe(tmp_path):
    """Mutual pins terminate (each visited once)."""
    store = RdfStore(tmp_path)
    store.load()
    a, b = URIRef(LIB), URIRef(ONT2)
    ga = store.dataset.get_context(a)
    gb = store.dataset.get_context(b)
    ga.add((a, PROMO["usesLibrary"], b))
    gb.add((b, PROMO["usesOntology"], a))
    scope = [str(i) for i in store.resolution_scope(LIB)]
    assert sorted(scope) == sorted([LIB, ONT2])


def test_create_artefact_canonicalises_trailing_slash(tmp_path):
    """Creation writes the canonical slash-free IRI: a stored
    ``…/x/`` graph is unreachable through graph_param/editable_param
    (both strip the slash), leaving the artefact orphaned — observed
    with a hub-created model whose pins silently resolved empty."""
    store = RdfStore(tmp_path)
    store.load()
    ont = str(store.ONTOLOGY_GRAPH_IRI)
    iri = store.create_artefact_graph(
        MODEL + "/", "Model", label="m",
        uses=[ont + "/"], uses_library=[LIB + "/"])

    assert str(iri) == MODEL
    g = store.dataset.get_context(URIRef(MODEL))
    assert len(g)                       # content lives on the canonical graph
    assert not len(store.dataset.get_context(URIRef(MODEL + "/")))
    assert str(g.value(URIRef(MODEL), PROMO["usesOntology"])) == ont
    assert str(g.value(URIRef(MODEL), PROMO["usesLibrary"])) == LIB

    # The pin is honoured by scope resolution — the artefact is not
    # an empty island.
    scope = {str(i) for i in store.resolution_scope(MODEL)}
    assert {MODEL, LIB, ont} <= scope

    # Re-creating the same line under either spelling is one graph.
    try:
        store.create_artefact_graph(MODEL + "/", "Model")
    except ValueError as exc:
        assert "already exists" in str(exc)
    else:                                # pragma: no cover
        raise AssertionError("slash variant created a shadow graph")


def test_fork_canonicalises_iris(tmp_path):
    """fork_graph shares the write boundary: source resolves
    leniently, the new artefact lands slash-free."""
    store = RdfStore(tmp_path)
    store.load()
    store.create_artefact_graph(LIB, "Library")
    new = store.fork_graph(LIB + "/", ONT2 + "/", label="fork")
    assert str(new) == ONT2
    assert len(store.dataset.get_context(URIRef(ONT2)))
    assert not len(store.dataset.get_context(URIRef(ONT2 + "/")))
