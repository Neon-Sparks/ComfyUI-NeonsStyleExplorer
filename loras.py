"""The LoRA explorer's gallery: folders as galleries, previews, trigger words.

The engine lives in `assets.py` and is shared with the checkpoint explorer —
two copies of this logic is how the two drifted apart in the first place. This
module is the LoRA-shaped view of it, keeping the names the rest of the package
already calls.
"""

from .assets import Gallery, UNSORTED, slug  # noqa: F401  (re-exported)

MAX_SHOTS = 8
MAX_TRIGGER = 400

_GALLERY = Gallery(kind="lora", folder_key="loras", storage="loras", text_field="triggers")

# --- listing -----------------------------------------------------------------

names = _GALLERY.names
split = _GALLERY.split
fingerprint = _GALLERY.fingerprint
reconcile = _GALLERY.reconcile


def entry(name):
    return _GALLERY.entry(name)


def catalog(refresh=False):
    """Everything the browser needs, under the keys it already expects."""
    data = _GALLERY.catalog(refresh)
    data["loras"] = data.pop("assets")
    return data


# --- trigger words -----------------------------------------------------------

load_triggers = _GALLERY.load_text
triggers_for = _GALLERY.text_for
set_triggers = _GALLERY.set_text

# --- favourites --------------------------------------------------------------

load_favourites = _GALLERY.load_favourites
is_favourite = _GALLERY.is_favourite
set_favourite = _GALLERY.set_favourite
toggle_favourite = _GALLERY.toggle_favourite

# --- previews ----------------------------------------------------------------

build_thumbs = _GALLERY.build_thumbs
shot_paths = _GALLERY.shot_paths
gallery_dir = _GALLERY.gallery_dir
manifest_path = _GALLERY.manifest_path
previews_dir = _GALLERY.previews_dir
manifest = _GALLERY.manifest
all_manifests = _GALLERY.all_manifests
shot_path = _GALLERY.shot_path
shot_filename = _GALLERY.shot_filename
set_cover = _GALLERY.set_cover
delete_shot = _GALLERY.delete_shot
delete_lora_shots = _GALLERY.delete_all_shots


def add_shot(name, source, prompt="", make_cover=True, max_shots=MAX_SHOTS):
    return _GALLERY.add_shot(name, source, prompt=prompt, make_cover=make_cover,
                             max_shots=max_shots)
