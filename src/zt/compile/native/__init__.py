"""
Native-code backend. Regenerates the image from the compiler's IR as straight Z80 —
primitives inlined or called through the IX link register, colon words reached by `CALL` —
instead of threaded cells walked by NEXT.
"""
