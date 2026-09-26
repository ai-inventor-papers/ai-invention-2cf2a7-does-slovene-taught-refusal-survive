"""Winogrande partial scoring (lm-eval convention) on the {query=continuation, choices=contexts, gold} schema."""


def wino_text(doc):
    return int(doc['gold'])


def wino_target(doc):
    return doc['query']


def wino_choice(doc):
    return list(doc['choices'])
