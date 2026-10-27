"""
The words on the figures of doc/figures (xrd_fit and xrd_seeds), in
English and in Russian: plain text. export_pgf.py and amorph_tex.py write
them into the macros of the tables as LaTeX, and the GUI draws them on the
previews (amorph_gui/figures.py).
"""

# English first: the language of the figures by default
LANGUAGES = ("en", "ru")

LABELS = {
    "en": {
        # xrd_fit
        "intensity": "Intensity, arb. un.",
        "data": "Experimental",
        "model_mean": "Model (mean)",
        "amorph_mean": "Amorphous (mean)",
        "xtal_mean": "Crystalline peaks (mean)",
        "bg_mean": "Background (mean)",
        "amorphous": "Amorphous",
        "note": "median and 50% interval",
        # xrd_seeds
        "counts": "Intensity, counts",
        "band": "model, 90%",
        "background": "background",
        "halo": "amorphous halo",
        "model": "model (mean)",
        "crystal": "crystalline peaks",
        "fraction": "amorphous fraction",
        "density": "posterior density",
        "pooled": "pooled",
        "seed": "seed {0}",
        "run": "run {0}",
        "title_seeds": ", seeds {0}",
        "title_seed": ", seed {0}",
        "count": "{0} seeds and pooled",
        "one": "the fraction",
        "spread": "spread of the medians of the seeds {0}",
        "one_run": "one run",
    },
    "ru": {
        "intensity": "Интенсивность, отн. ед.",
        "data": "Эксперимент",
        "model_mean": "Модель (среднее)",
        "amorph_mean": "Аморфная часть (среднее)",
        "xtal_mean": "Кристаллические пики (среднее)",
        "bg_mean": "Фон (среднее)",
        # In percent: "доля" is 0-1 everywhere else
        "amorphous": "Степень аморфности",
        "note": "медиана и 50% интервал",
        "counts": "Интенсивность, имп.",
        "band": "модель, 90%",
        "background": "фон",
        "halo": "аморфное гало",
        "model": "модель (среднее)",
        "crystal": "кристаллические пики",
        "fraction": "аморфная доля",
        "density": "апостериорная плотность",
        "pooled": "вместе",
        "seed": "сид {0}",
        "run": "прогон {0}",
        "title_seeds": ", сиды {0}",
        "title_seed": ", сид {0}",
        "count": "по сидам ({0}) и вместе",
        "one": "доля",
        "spread": "разброс медиан сидов {0}",
        "one_run": "один прогон",
    },
}
