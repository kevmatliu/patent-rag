def register_heif_opener() -> None:
    """
    Minimal local shim for DECIMER's optional HEIF support.
    Our patent pipeline operates on PNG crops, so a no-op is sufficient here.
    """
    return None
