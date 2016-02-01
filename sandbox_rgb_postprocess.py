import cPickle as pickle
import numpy as np
import os
from sys import maxsize
from astropy.table import Table

import AnniesLasso as tc

# These are taken from sandbox_rgb.py
# For ~50 pixels, try some Lambda values.
# Recommended pixels from Melissa, in vacuum.
wavelengths = [
    16795.77313988085, # --> continuum
    15339.0, # --> Teff sensitivity
    15720,   # --> Teff sensitivity
    15770,   # --> logg sensitivity
    16811.5, # --> Logg sensitivity
    15221.5, # --> [Fe/H] sensitivity
    16369,   # --> [alpha/Fe] sensitivity
]

# These lines were all given in air, so I have converted them to vacuum.
# Three Fe I lines from Smith et al. (2013)
# Air: 15490.339, 15648.510, 15964.867
# Vac: [15494.571901901722, 15652.785921456885, 15969.22897071544]
wavelengths.extend(
    [15494.571901901722, 15652.785921456885, 15969.22897071544])

# Two Mg I lines from Smith et al. (2013)
# Air: 15765.8, 15879.5
# Vac: [15770.107823467057, 15883.838750072413]
wavelengths.extend(
    [15770.107823467057, 15883.838750072413])

# Two Al I lines from Smith et al. (2013)
# Air: 16718.957, 16763.359
# Vac: [16723.524113765838, 16767.938194147067]
wavelengths.extend(
    [16723.524113765838, 16767.938194147067])

# Two Si II lines from Smith et al. (2013)
# Air: 15960.063, 16060.009
# Vac: [15964.42366396639, 16064.396850911658]
wavelengths.extend(
    [15964.42366396639, 16064.396850911658])

# Two Ca I lines from Smith et al. (2013)
# Air: 16150.763, 16155.236
# Vac: [16155.17553813612, 16159.649754913306]
wavelengths.extend(
    [16155.17553813612, 16159.649754913306])

# Two Cr I lines from Smith et al. (2013)
# Air: 15680.063, 15860.214
# Vac: [15684.347503529489, 15864.547504173868]
wavelengths.extend(
    [15684.347503529489, 15864.547504173868])

# One Co I line from Smith et al. (2013)
# Air: 16757.7
# Vac: 16762.27765450469
wavelengths.extend(
    [16762.27765450469])

# One V I line from Smith et al. (2013) 
# Air: 15924.
# Vac: 15928.350854428922
wavelengths.extend(
    [15928.350854428922])
    
# Two Ni I lines from Smith et al. (2013)
# Air: 16589.295, 16673.711
# Vac: [16593.826837590106, 16678.26580389432]
wavelengths.extend(
    [16593.826837590106, 16678.26580389432])

# Two K I line from Smith et al. (2013)
# Air: 15163.067,15168.376
# Vac: [15167.21089680259, 15172.521340566429]
wavelengths.extend(
    [15167.21089680259, 15172.521340566429])

# Two Mn I lines from Smith et al. (2013)
# Air: 15217., 15262.
# Vac:  [15221.158563809242, 15266.17080169663]
wavelengths.extend(
     [15221.158563809242, 15266.17080169663])


i, models = 0, []
model_filename = "apogee-rg-validation-{}.pkl"
while os.path.exists(model_filename.format(i)):
    models.append(tc.load_model(model_filename.format(i)))
    i += 1


latex_labels = [r"{T_{\rm eff}}", r"\log{g}"] \
    + [r"{\rm [%s/H]}" % each.split("_")[0] for each in latex_labels[2:]]

# Plot Lambda vs theta for the different models.
figs = tc.diagnostics.pixel_regularization_effectiveness(models,
    wavelengths[:4], latex_labels=latex_labels)

raise a

    )


def pixel_regularization_effectiveness(models, wavelengths, label_names=None,
    latex_labels=None, same_limits=False,
    show_legend=True, **kwargs):