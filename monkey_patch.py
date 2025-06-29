from SmartApi.smartConnect import SmartConnect

# Store original __init__
_original_init = SmartConnect.__init__

# Patch to remove 'proxies' key if present
def _patched_init(self, *args, **kwargs):
    kwargs.pop("proxies", None)
    return _original_init(self, *args, **kwargs)

# Apply the patch
SmartConnect.__init__ = _patched_init
