"""Suggesters: modules that propose boxes and labels (dom, rule, prior, model, llm).

`default_suggesters` is the registry: the suggesters the server's Suggest button and
`annotool suggest` run, in this order. Adding a suggester means writing a class with an
`id` and a `suggest(context)` method (see `base.Suggester`) and listing it here.
"""

from annotool.suggest.base import Suggester
from annotool.taxonomy import Taxonomy


def default_suggesters(taxonomy: Taxonomy) -> list[Suggester]:
    """The registered suggesters, in run order: dom → rule → prior.

    The rule (roadmap 4.3) and prior (4.4) suggesters will join the DOM one here.
    """
    from annotool.suggest.dom import DomSuggester

    return [DomSuggester.from_taxonomy(taxonomy)]
