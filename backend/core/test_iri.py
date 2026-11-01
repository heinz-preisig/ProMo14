"""Shape tests for the §26 IRI constructors — the conventions are
asserted here once so a drift in any caller breaks loudly."""

from rdflib import URIRef

from backend.core.iri import (
    arc_type_iri,
    assignment_iri,
    assignments_graph_iri,
    canonical_graph_iri,
    child_iri,
    composite_iri,
    equation_iri,
    expression_iri,
    f_factor_iri,
    is_absolute,
    local_name,
    model_arc_iri,
    model_iri,
    model_node_iri,
    occurrence_prefix,
    variable_iri,
    vocab_iri,
    vocab_ns_iri,
)

# Canonical artefact IRIs are slash-free names; the trailing-slash
# spelling only survives as input (``?graph=``, old data).
LIB = "https://w3id.org/promo/library"
LIB_SLASH = LIB + "/"
MODEL = "https://example.org/test-model"
ONT = "https://w3id.org/promo/ontology"


def test_vocabulary_members():
    assert str(vocab_iri(LIB, "d")) == LIB + "#d"
    assert str(variable_iri(LIB, "fQy")) == LIB + "#fQy"
    assert str(equation_iri(LIB, "E_3")) == LIB + "#E_3"
    # trailing-# bases normalise
    assert str(vocab_iri(LIB + "#", "x")) == LIB + "#x"


def test_model_records():
    # '/'-children — uniform on slash-free artefact IRIs, and a
    # trailing-slash input normalises to the same spelling
    assert str(model_node_iri(MODEL, 3)) == MODEL + "/Node_3"
    assert str(model_node_iri(LIB_SLASH, 3)) == LIB + "/Node_3"
    assert str(model_arc_iri(MODEL, 7)) == MODEL + "/Arc_7"
    assert str(model_iri(MODEL)) == MODEL + "/Model"
    assert str(composite_iri(MODEL, 7)) == MODEL + "/Composite_7"


def test_canonical_graph_iri():
    assert canonical_graph_iri(LIB_SLASH) == LIB
    assert canonical_graph_iri(MODEL) == MODEL
    assert canonical_graph_iri(ONT) == ONT


def test_subordinate_resources():
    eq = URIRef(LIB + "#E_2")
    assert str(expression_iri(eq)) == LIB + "#E_2/expression"
    assert assignments_graph_iri(MODEL) == MODEL + "/assignments"
    assert str(assignment_iri(MODEL + "/assignments",
                              ONT + "#etype_capacity")) == \
        MODEL + "/assignments#assignment_etype_capacity"
    assert occurrence_prefix(MODEL + "/Composite_2") == \
        MODEL + "/Composite_2/"
    assert str(child_iri(MODEL + "/", "submodel")) == MODEL + "/submodel"


def test_synthesised_shapes():
    assert f_factor_iri(ONT, "conv") == URIRef(ONT + "#F_conv")
    assert arc_type_iri("token-flow") == \
        "https://w3id.org/promo#ArcType/token-flow"
    assert arc_type_iri(None) == "https://w3id.org/promo#ArcType/generic"
    assert vocab_ns_iri("ArcType/reference") == \
        "https://w3id.org/promo#ArcType/reference"


def test_local_name_and_guard():
    assert local_name(LIB + "#x") == "x"
    assert local_name(MODEL + "/Composite_2") == "Composite_2"
    assert local_name(MODEL + "/Node_4") == "Node_4"
    assert local_name("promo:y") == "promo:y"   # opaque, no separator
    assert is_absolute("https://a/b#c")
    assert is_absolute("http://a/b")
    assert not is_absolute("promo:x")
    assert not is_absolute("ArcType/token-flow")
