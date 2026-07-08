"""Request schemas (Pydantic v2).

Auth is the exemplar; other domains adopt schemas opportunistically as their
routes get touched. Schemas parse/normalize the payload; the error strings,
status codes, and check ORDER of the previous hand-rolled validation are
preserved exactly (see each schema's first_error()).
"""
