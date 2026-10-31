"""Knowledge engine package exports.

Keep the LangRAG import lazy so importing helper modules such as
``components.knowledge_engine.query_rewrite`` does not require optional parser
dependencies.
"""


def __getattr__(name: str):
    if name == "LangRAG":
        from .langrag import LangRAG

        return LangRAG
    raise AttributeError(name)


__all__ = ["LangRAG"]
