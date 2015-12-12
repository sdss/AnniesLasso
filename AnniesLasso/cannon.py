#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
A pedestrian version of The Cannon.
"""

from __future__ import (division, print_function, absolute_import,
                        unicode_literals)

__all__ = ["CannonModel"]

import logging
import numpy as np
import scipy.optimize as op

from . import (model, utils)

logger = logging.getLogger(__name__)


class CannonModel(model.BaseCannonModel):
    """
    A generalised Cannon model for the estimation of arbitrary stellar labels.

    :param labelled_set:
        A set of labelled objects. The most common input form is a table with
        columns as labels, and stars/objects as rows.

    :type labelled_set:
        :class:`~astropy.table.Table`, numpy structured array

    :param normalized_flux:
        An array of normalized fluxes for stars in the labelled set, given as
        shape `(num_stars, num_pixels)`. The `num_stars` should match the number
        of rows in `labelled_set`.

    :type normalized_flux:
        :class:`np.ndarray`

    :param normalized_ivar:
        An array of inverse variances on the normalized fluxes for stars in the
        labelled set. The shape of the `normalized_ivar` array should match that
        of `normalized_flux`.

    :type normalized_ivar:
        :class:`np.ndarray`

    :param dispersion: [optional]
        The dispersion values corresponding to the given pixels. If provided, 
        this should have length `num_pixels`.

    :param threads: [optional]
        Specify the number of parallel threads to use. If `threads > 1`, the
        training and prediction phases will be automagically parallelised.

    :param pool: [optional]
        Specify an optional multiprocessing pool to map jobs onto.
        This argument is only used if specified and if `threads > 1`.
    """
    def __init__(self, *args, **kwargs):
        super(CannonModel, self).__init__(*args, **kwargs)


    @model.requires_model_description
    def train(self, fixed_scatter=False, progressbar=True, **kwargs):
        """
        Train the model based on the labelled set using the given vectorizer.

        :param fixed_scatter: [optional]
            Fix the scatter terms and do not solve for them during the training
            phase. If set to `True`, the `s2` attribute must be already set.

        :param progressbar: [optional]
            Show a progress bar.
        """
        
        if fixed_scatter and self.s2 is None:
            raise ValueError("scatter attribute (s2) must be set "
                             "before training if fixed_scatter is set to True")

        # Initialize the scatter.
        p0_scatter = np.sqrt(self.s2) if fixed_scatter \
            else 0.01 * np.ones_like(self.dispersion)

        # Prepare details about any progressbar to show.
        M, N = self.normalized_flux.shape
        message = None if not progressbar else \
            "Training {0} with {1} stars and {2} pixels/star".format(
                type(self).__name__, M, N)

        # Prepare the method and arguments.
        fitter = kwargs.pop("function", _fit_pixel)
        args = [self.normalized_flux.T, self.normalized_ivar.T, p0_scatter]
        args.extend(kwargs.pop("additional_args", []))
        kwds = {
            "fixed_scatter": fixed_scatter,
            "design_matrix": self.design_matrix
        }
        kwds.update(kwargs)

        # Wrap the function so we can parallelize it out.
        f = utils.wrapper(fitter, None, kwds, N, message=message)

        # Time for work.
        mapper = map if self.pool is None else self.pool.map
        results = np.array(mapper(f, [row for row in zip(*args)]))

        # Unpack the results.
        self.theta, self.s2 = (results[:, :-1], results[:, -1]**2)
        return None


    @model.requires_training_wheels
    def predict(self, labels, **kwargs):
        """
        Predict spectra from the trained model, given the labels.

        :param labels:
            The label values to predict model spectra of. The length and order
            should match what is required of the vectorizer
            (`CannonModel.vectorizer.label_names`).
        """
        return np.dot(self.theta, self.vectorizer(labels).T).T


    @model.requires_training_wheels
    def fit(self, normalized_flux, normalized_ivar, **kwargs):
        """
        Solve the labels for the given normalized fluxes and inverse variances.

        :param normalized_flux:
            The normalized fluxes. These should be on the same dispersion scale
            as the trained data.

        :param normalized_ivar:
            The inverse variances of the normalized flux values. This should
            have the same shape as `normalized_flux`.

        :returns:
            The labels.
        """

        normalized_flux = np.atleast_2d(normalized_flux)
        normalized_ivar = np.atleast_2d(normalized_ivar)

        N = normalized_flux.shape[0]
        pb_kwds = {
            "message": "Fitting spectra to {} stars".format(N),
            "size": 100 if kwargs.pop("progressbar", True) and N > 10 else -1
        }
        
        labels = np.nan * np.ones((N, len(self.vectorizer.label_names)))
        # ISSUE: TODO: parallelism breaks.
        #if self.pool is None:
        for i in utils.progressbar(range(N), **pb_kwds):
            labels[i], _ = _fit_spectrum(
                self.vectorizer, self.theta, self.s2,
                normalized_flux[i], normalized_ivar[i], **kwargs)
        """
        else:
            processes = { i: self.pool.apply_async(_fit_spectrum,
                    args=(self.vectorizer, self.theta, self.s2,
                        normalized_flux[i], normalized_ivar[i]),
                    kwds=kwargs) \
                for i in range(N) }

            for i, process in utils.progressbar(processes.items(), **pb_kwds):
                labels[i], _ = process.get()
        """
        return labels




def _estimate_label_vector(theta, scatter, normalized_flux, normalized_ivar,
    **kwargs):
    """
    Perform a matrix inversion to estimate the values of the label vector given
    some normalized fluxes and associated inverse variances.

    :param theta:
        The theta coefficients that have been trained from the labelled set.

    :param scatter:
        The pixel scatter that have been trained from the labelled set.

    :param normalized_flux:
        The normalized flux values. These should be on the same dispersion scale
        as the labelled data set.

    :param normalized_ivar:
        The inverse variance of the normalized flux values. This should have the
        same shape as `normalized_flux`.
    """

    inv_var = normalized_ivar/(1. + normalized_ivar * scatter**2)
    A = np.dot(theta.T, inv_var[:, None] * theta)
    B = np.dot(theta.T, inv_var * normalized_flux)
    return np.linalg.solve(A, B)


def _fit_spectrum(vectorizer, theta, scatter, normalized_flux,
    normalized_ivar, **kwargs):
    """
    Solve the labels for given pixel fluxes and uncertainties for a single star.

    :param vectorizer:
        The model vectorizer.

    :param theta:
        The trained theta coefficients for the model.

    :param scatter:
        The trained pixel scatter terms for the model.

    :param normalized_flux:
        The normalized fluxes. These should be on the same dispersion scale
        as the trained data.

    :param normalized_ivar:
        The 1-sigma uncertainties in the fluxes. This should have the same
        shape as `normalized_flux`.

    :returns:
        The labels and covariance matrix.
    """

    # Get an initial estimate of the label vector from a matrix inversion,
    # and then ask the vectorizer to interpret that label vector into the 
    # (approximate) values of the labels that could have produced that 
    # label vector.
    label_vector = _estimate_label_vector(theta, scatter,
        normalized_flux, normalized_ivar)
    initial = vectorizer.get_approximate_labels(label_vector)

    # Solve for the parameters.
    inv_var = normalized_ivar/(1. + normalized_ivar * scatter**2)
    
    kwds = {
        "p0": initial,
        "maxfev": np.inf,
        "sigma": np.sqrt(1.0/inv_var),
        "absolute_sigma": True
    }
    kwds.update(kwargs)

    function = lambda t, *l: np.dot(t, vectorizer(l).T).T.flatten()
    labels, cov = op.curve_fit(function, theta, normalized_flux, **kwds)
    return (labels, cov)


def _fit_pixel(normalized_flux, normalized_ivar, scatter, design_matrix,
    fixed_scatter=False, **kwargs):
    """
    Return the optimal vectorizer coefficients and variance term for a pixel
    given the normalized flux, the normalized inverse variance, and the design
    matrix.

    :param normalized_flux:
        The normalized flux values for a given pixel, from all stars.

    :param normalized_ivar:
        The inverse variance of the normalized flux values for a given pixel,
        from all stars.

    :param design_matrix:
        The design matrix for the spectral model.

    :param scatter:
        Fit the data using a fixed scatter term. If this value is set to None,
        then the scatter will be calculated.

    :returns:
        The optimised label vector coefficients and scatter for this pixel, even
        if it was supplied by the user.
    """
    logger.debug("Fitting pixel")

    theta, ATCiAinv, inv_var = _fit_theta(normalized_flux, normalized_ivar,
        scatter, design_matrix)

    # Singular matrix or fixed scatter?
    if ATCiAinv is None or fixed_scatter:
        return np.hstack([theta, scatter if fixed_scatter else np.inf])

    # Optimise the pixel scatter, and at each pixel scatter value we will 
    # calculate the optimal vector coefficients for that pixel scatter value.
    op_scatter, fopt, direc, n_iter, n_funcs, warnflag = op.fmin_powell(
        _fit_pixel_with_fixed_scatter, scatter,
        args=(normalized_flux, normalized_ivar, design_matrix),
        maxiter=np.inf, maxfun=np.inf, disp=False, full_output=True)

    if warnflag > 0:
        logger.warning("Warning: {}".format([
            "Maximum number of function evaluations made during optimisation.",
            "Maximum number of iterations made during optimisation."
            ][warnflag - 1]))

    theta, ATCiAinv, inv_var = _fit_theta(normalized_flux, normalized_ivar,
        op_scatter, design_matrix)
    logger.debug("Returning {0} {1}".format(theta, op_scatter))
    return np.hstack([theta, op_scatter])


def _fit_pixel_with_fixed_scatter(scatter, normalized_flux, normalized_ivar,
    design_matrix, **kwargs):
    """
    Fit the normalized flux for a single pixel (across many stars) given some
    pixel variance term, and return the best-fit theta coefficients.

    :param scatter:
        The additional scatter to adopt in the pixel.

    :param normalized_flux:
        The normalized flux values for a single pixel across many stars.

    :param normalized_ivar:
        The inverse variance of the normalized flux values for a single pixel
        across many stars.

    :param design_matrix:
        The design matrix for the model.
    """

    theta, ATCiAinv, inv_var = _fit_theta(normalized_flux, normalized_ivar,
        scatter, design_matrix)

    return_theta = kwargs.get("__return_theta", False)
    if ATCiAinv is None:
        return np.inf if not return_theta else (np.inf, theta)

    # We take inv_var back from _fit_theta because it is the same quantity we 
    # need to calculate, and it saves us one operation.
    Q   = model._chi_sq(theta, design_matrix, normalized_flux, inv_var) \
        + model._log_det(inv_var)
    return (Q, theta) if return_theta else Q


def _fit_theta(normalized_flux, normalized_ivar, scatter, design_matrix):
    """
    Fit theta coefficients to a set of normalized fluxes for a single pixel.

    :param normalized_flux:
        The normalized fluxes for a single pixel (across many stars).

    :param normalized_ivar:
        The inverse variance of the normalized flux values for a single pixel
        across many stars.

    :param scatter:
        The additional scatter to adopt in the pixel.

    :param design_matrix:
        The model design matrix.

    :returns:
        The label vector coefficients for the pixel, the inverse variance matrix
        and the total inverse variance.
    """

    ivar = normalized_ivar/(1. + normalized_ivar * scatter**2)
    CiA = design_matrix * np.tile(ivar, (design_matrix.shape[1], 1)).T
    try:
        ATCiAinv = np.linalg.inv(np.dot(design_matrix.T, CiA))
    except np.linalg.linalg.LinAlgError:
        #if logger.getEffectiveLevel() == logging.DEBUG: raise
        return (np.hstack([1, [0] * (design_matrix.shape[1] - 1)]), None, ivar)

    ATY = np.dot(design_matrix.T, normalized_flux * ivar)
    theta = np.dot(ATCiAinv, ATY)

    return (theta, ATCiAinv, ivar)