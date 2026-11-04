"""What Muse Wonder is asked to do with a photo or a voice note before the turn starts.

The advisor reads text. These two prompts turn what the customer sent into text, and the
turn goes on as if they had typed it, so the searcher, the judge and the citation check do not
change. Neither prompt may name a product: the catalog decides that, with a datasheet behind it.
"""

PHOTO_PROMPT = """\
A farmer sent this photo to their farm-input distributor. Describe what it shows, in plain words, \
in at most three sentences: the crop if you can tell it, the part of the plant, the damage or the \
insect you see, and the pest or disease it most resembles, saying how sure you are. Do not name \
any commercial product, dose or treatment. If it is not a plant or a pest, say what it is."""
"""A description, not a diagnosis: the customer's own words would be the same kind of evidence."""

VOICE_PROMPT = """\
Transcribe this voice note word for word, in the language it was spoken. Return only the \
transcript, with no comment. If nothing can be understood, return an empty answer."""
