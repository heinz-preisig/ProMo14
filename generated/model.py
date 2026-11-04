import numpy as np
import scipy.sparse
import scipy.optimize
from scipy.optimize import fsolve
import json as _json
import os.path as _osp

_DIR = (_osp.dirname(_osp.abspath(__file__)) if '__file__' in globals() else '')
if '_DATA' not in globals():
    _DATA = _json.load(open(_osp.join(_DIR, "model_data.json")))

def _mx(n):
    e = _DATA['matrices'][n]
    return scipy.sparse.coo_array(        (e['v'], (e['i'], e['j'])),        shape=(e['m'], e['n']))

def _tab(n):
    e = _DATA['values'][n]
    return np.array(e['flat']).reshape(e['dims'])

def _ictab(n):
    e = _DATA['ics'][n]
    return np.array(e['flat']).reshape(e['dims'])

F_conv_convection_transport = _mx("F_conv_convection_transport")  # F over [1 x 2]
F_conv_lumped = _mx("F_conv_lumped")  # F over [1 x 1]

def derivative(t, y, par, out=None):
    dy = np.zeros(1)
    V_57_lumped = y[0:1].reshape((1, 1))
    V_39 = _tab("V_39")  # value cells
    V_54 = _tab("V_54")  # value cells
    V_57_convection_transport = _tab("V_57_convection_transport")  # value cells
    V_34_environment = _tab("V_34_environment")  # value cells
    V_34_lumped = _tab("V_34_lumped")  # value cells
    V_34_convection_transport = np.concatenate([np.ravel(V_34_environment[[0]]), np.ravel(V_34_lumped[[0]])])  # port gather
    def _balance(u):
        V_56_convection_transport = u[0:2].reshape((2, 1))
        dV_57_lumped = u[2:3].reshape((1, 1))
        V_56_lumped = V_56_convection_transport[[1]]  # port gather
        _r0 = np.ravel((_d(np.broadcast_to(np.asarray(( ( V_39 * V_54 ) * ( V_34_convection_transport @ F_conv_convection_transport ) )).reshape((1, 1)), (2, 1)))) - V_56_convection_transport)
        _r1 = np.ravel((_d(np.asarray(np.sum(( F_conv_lumped.multiply(np.asarray(V_56_lumped)) ), axis=0)).reshape((1, 1)))) - dV_57_lumped)
        _r2 = np.ravel((_d(np.broadcast_to(np.asarray(np.sum(( F_conv_convection_transport.multiply(np.asarray(V_56_convection_transport)) ), axis=0)).reshape((1, 1)), (2, 1)))) - V_57_convection_transport)
        return np.concatenate([_r0, _r1, _r2])
    _u = _solve_balance(_balance, 3)
    V_56_convection_transport = _u[0:2].reshape((2, 1))
    dV_57_lumped = _u[2:3].reshape((1, 1))
    dy[0:1] = np.ravel(dV_57_lumped)
    if out is not None:  # §21 outputs
        out["V_56_convection_transport"] = _d(V_56_convection_transport)
    return dy

def outputs(t, y, par):
    _o = {}
    derivative(t, y, par, out=_o)
    return _o

def initial(par, steady_state=False):
    V_39 = _tab("V_39")  # value cells
    V_54 = _tab("V_54")  # value cells
    V_57_convection_transport = _tab("V_57_convection_transport")  # value cells
    V_34_environment = _tab("V_34_environment")  # value cells
    V_34_lumped = _tab("V_34_lumped")  # value cells
    V_34_convection_transport = np.concatenate([np.ravel(V_34_environment[[0]]), np.ravel(V_34_lumped[[0]])])  # port gather
    def _t0(u):  # t=0 residual system
        V_57_lumped = u[0:1].reshape((1, 1))
        V_56_convection_transport = u[1:3].reshape((2, 1))
        dV_57_lumped = u[3:4].reshape((1, 1))
        if steady_state:
            total_diff = lambda x, y: np.zeros_like(x)  # der = 0
        V_56_lumped = V_56_convection_transport[[1]]  # port gather
        _r0 = (_d(np.broadcast_to(np.asarray(( ( V_39 * V_54 ) * ( V_34_convection_transport @ F_conv_convection_transport ) )).reshape((1, 1)), (2, 1)))) - V_56_convection_transport
        _r1 = (_d(np.asarray(np.sum(( F_conv_lumped.multiply(np.asarray(V_56_lumped)) ), axis=0)).reshape((1, 1)))) - dV_57_lumped
        _r2 = (_d(np.broadcast_to(np.asarray(np.sum(( F_conv_convection_transport.multiply(np.asarray(V_56_convection_transport)) ), axis=0)).reshape((1, 1)), (2, 1)))) - V_57_convection_transport
        _rs = [np.ravel(_r0), np.ravel(_r1), np.ravel(_r2)]
        if steady_state:
            _rs += [np.ravel(dV_57_lumped)]  # der = 0
        else:
            _e0 = (_ictab("V_57_lumped")) - V_57_lumped  # IC pin
            _rs += [np.ravel(_e0)]
        return np.concatenate(_rs) if _rs else np.zeros_like(u)
    _u = _solve_balance(_t0, 4)
    V_57_lumped = _u[0:1].reshape((1, 1))
    return np.concatenate([np.ravel(V_57_lumped)])


def _d(x):
    return x.toarray() if hasattr(x, 'toarray') else x

def _solve_balance(fun, size):
    guess = np.zeros(size)
    if size == 0:
        if not np.allclose(fun(guess), 0, atol=1e-8):
            raise ValueError('prescribed balance is inconsistent')
        return guess
    result = scipy.optimize.least_squares(fun, guess, ftol=1e-12, xtol=1e-12, gtol=1e-12)
    if not result.success or not np.all(np.isfinite(result.fun)) or np.max(np.abs(result.fun), initial=0) > 1e-8:
        raise ValueError('prescribed balance solve failed: ' + result.message)
    if np.linalg.matrix_rank(result.jac) < size:
        raise ValueError('prescribed balance system is underdetermined')
    return result.x