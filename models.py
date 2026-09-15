"""The checkpoint explorer's gallery.

The same engine as the LoRA explorer (`assets.py`), pointed at ComfyUI's
checkpoints folder with its own storage under `user/models/`. Its per-file text
is **notes** rather than trigger words: a checkpoint does not want words in the
prompt, but it usually does want a reminder — the sampler, the CFG, the
resolution it likes.
"""

from .assets import Gallery, UNSORTED, slug  # noqa: F401  (re-exported)

MAX_SHOTS = 8
MAX_NOTE = 400

# Both places ComfyUI keeps a base model. Checkpoints carry their own CLIP and
# VAE; a diffusion model (Flux and friends) is the UNET alone, so the loader
# treats them differently while the gallery treats them alike.
FOLDERS = ("checkpoints", "diffusion_models")

_GALLERY = Gallery(kind="model", folder_key=FOLDERS, storage="models",
                   text_field="notes")
source_of = _GALLERY.source_of

# --- listing -----------------------------------------------------------------

names = _GALLERY.names
split = _GALLERY.split
fingerprint = _GALLERY.fingerprint
reconcile = _GALLERY.reconcile


def entry(name):
    return _GALLERY.entry(name)


def catalog(refresh=False):
    """Everything the browser needs, with the checkpoints under `models`."""
    data = _GALLERY.catalog(refresh)
    data["models"] = data.pop("assets")
    return data


# --- notes -------------------------------------------------------------------

load_notes = _GALLERY.load_text
notes_for = _GALLERY.text_for
set_notes = _GALLERY.set_text

# --- favourites --------------------------------------------------------------

load_favourites = _GALLERY.load_favourites
is_favourite = _GALLERY.is_favourite
set_favourite = _GALLERY.set_favourite
toggle_favourite = _GALLERY.toggle_favourite

# --- previews ----------------------------------------------------------------

gallery_dir = _GALLERY.gallery_dir
manifest_path = _GALLERY.manifest_path
previews_dir = _GALLERY.previews_dir
manifest = _GALLERY.manifest
all_manifests = _GALLERY.all_manifests
shot_path = _GALLERY.shot_path
shot_filename = _GALLERY.shot_filename
set_cover = _GALLERY.set_cover
delete_shot = _GALLERY.delete_shot
delete_model_shots = _GALLERY.delete_all_shots


def add_shot(name, source, prompt="", make_cover=True, max_shots=MAX_SHOTS):
    return _GALLERY.add_shot(name, source, prompt=prompt, make_cover=make_cover,
                             max_shots=max_shots)
